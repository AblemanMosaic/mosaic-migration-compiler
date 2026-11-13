import hashlib,json,unittest
from .helpers import refuses
from mosaic_mmc import canonical,decode,digest

class CodecTests(unittest.TestCase):
    def test_known_encoding(self):
        self.assertEqual(canonical({'z':'\u00e9','a':[None,True,-2]}),b'{"a":[null,true,-2],"z":"\xc3\xa9"}')
    def test_independent_known_digest(self):
        body={'a':1};expected=hashlib.sha256(b'MMC/T1/canonical-model\0{"a":1}').hexdigest()
        self.assertEqual(digest('canonical-model',body),expected)
    def test_domains_distinct(self):self.assertNotEqual(digest('canonical-model',{}),digest('workflow-ir',{}))
    def test_noncanonical_flag(self):
        self.assertEqual(decode(b'{ "x":1 }'),{'x':1});refuses(self,lambda:decode(b'{ "x":1 }',canonical_only=True),'MMC_NOT_CANONICAL')
    def test_negative_zero(self):
        self.assertEqual(canonical(decode(b'-0')),b'0');refuses(self,lambda:decode(b'-0',canonical_only=True),'MMC_NOT_CANONICAL')
    def test_no_unicode_normalization(self):self.assertNotEqual(canonical('e\u0301'),canonical('\u00e9'))
    def test_boolean_is_not_integer(self):self.assertNotEqual(canonical(True),canonical(1))
    def test_null_is_not_missing(self):self.assertNotEqual(canonical({'x':None}),canonical({}))
    def test_list_order(self):self.assertNotEqual(canonical([1,2]),canonical([2,1]))
    def test_exact_subclasses_refused(self):
        class X(int):pass
        refuses(self,lambda:canonical(X(1)),'MMC_VALUE_TYPE')
    def test_cycle(self):
        value=[];value.append(value);refuses(self,lambda:canonical(value),'MMC_VALUE_CYCLE')
    def test_repeated_subobject_not_cycle(self):
        a={'v':1};self.assertEqual(canonical([a,a]),b'[{"v":1},{"v":1}]')
    def test_node_budget(self):refuses(self,lambda:canonical([None]*50000),'MMC_NODE_LIMIT')
    def test_domain_refusal(self):refuses(self,lambda:digest('eval',{}),'MMC_DOMAIN_UNSUPPORTED')

for index,raw in enumerate([b'{"x":1,"x":2}',b'NaN',b'Infinity',b'-Infinity',b'1.0',b'1e3',b'"\\udc00"',b'\xff',b'\xef\xbb\xbf{}',b'{}{}',b'{',b'9223372036854775808',b'-9223372036854775809']):
    def test(self,raw=raw):refuses(self,lambda:decode(raw))
    setattr(CodecTests,f'test_invalid_json_{index:02}',test)
for index,value in enumerate([0,1,-1,2**63-1,-2**63,True,False,None,[],{},'\n\t\u0000','😀','é','汉字']):
    def test(self,value=value):self.assertEqual(canonical(decode(canonical(value),canonical_only=True)),canonical(value))
    setattr(CodecTests,f'test_roundtrip_{index:02}',test)
