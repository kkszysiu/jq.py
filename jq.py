import json
from cffi import FFI
ffi = FFI()

ffi.cdef("""
    struct jv_refcnt;

    typedef struct {
        unsigned char kind_flags;
        unsigned char pad_;
        unsigned short offset;  /* array offsets */
        int size;
        ...;
    } jv;

    typedef struct jq_state jq_state;
    typedef void (*jq_err_cb)(void *, jv);

    jq_state *jq_init(void);
    int jq_compile(jq_state *, const char* str);
    void jq_start(jq_state *, jv value, int flags);
    jv jq_next(jq_state *);

    jv jv_null(void);
    jv jv_string(const char*);
    const char* jv_string_value(jv);

    void jv_free(jv);

    jv jv_dump_string(jv, int flags);

    typedef enum {
        JV_PARSE_EXPLODE_TOPLEVEL_ARRAY = 1
    } jv_parser_flags;
    struct jv_parser;
    struct jv_parser* jv_parser_new(jv_parser_flags);
    void jv_parser_set_buf(struct jv_parser*, const char*, int, int);
    jv jv_parser_next(struct jv_parser*);
    void jv_parser_free(struct jv_parser*);

    int jv_is_valid(jv x);
""")

jqlib = ffi.verify("#include <jq.h>\n#include <jv.h>",
                 libraries=['jq'])

class JQ(object):
    def __init__(self, program):
        program_bytes = program.encode("utf8")
        self.jq = jqlib.jq_init()

        if not self.jq:
            raise Exception("jq_init failed")

        compiled = jqlib.jq_compile(self.jq, program_bytes)

        if not compiled:
            raise ValueError("program was not valid")

    def transform(self, input, raw_input=False, raw_output=False, multiple_output=False):
        string_input = input if raw_input else json.dumps(input)

        bytes_input = string_input.encode("utf8")
        result_bytes = self._string_to_strings(bytes_input)
        result_strings = map(lambda s: ffi.string(s).decode("utf8"), result_bytes)

        if raw_output:
            return "\n".join(result_strings)
        elif multiple_output:
            return [json.loads(s) for s in result_strings]
        else:
            return json.loads(next(iter(result_strings)))

    def _string_to_strings(self, input):
        parser = jqlib.jv_parser_new(0)
        jqlib.jv_parser_set_buf(parser, input, len(input), 0)

        value = ffi.new("jv*")
        results = []
        while True:
            value = jqlib.jv_parser_next(parser)
            if jqlib.jv_is_valid(value):
                self._process(value, results)
            else:
                break

        jqlib.jv_parser_free(parser)

        return results

    def _process(self, value, output):
        jq_flags = 0
        jqlib.jq_start(self.jq, value, jq_flags)

        result = ffi.new("jv*")
        dumpopts = 0
        dumped = ffi.new("jv*")

        while True:
            result = jqlib.jq_next(self.jq)
            if not jqlib.jv_is_valid(result):
                jqlib.jv_free(result)
                return
            else:
                dumped = jqlib.jv_dump_string(result, dumpopts)
                output.append(jqlib.jv_string_value(dumped))
                jqlib.jv_free(dumped)

jq = JQ