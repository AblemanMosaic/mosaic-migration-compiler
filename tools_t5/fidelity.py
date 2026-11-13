"""A local gate cannot certify production, native mediation or comparative economics."""
from mosaic_mmc import canonical
from mosaic_mmc.errors import require

def check_claims(value):
    expected={'native_pippi':'NOT_BOUND','independent_review':'NOT_PERFORMED',
        'production_evidence':False,'productivity_claim':'NOT_ESTABLISHED','public_release':'NOT_CLEARED',
        'qualification_scope':'FINITE_LOCAL_SIMULATION','authority_effect':'NONE'}
    require(canonical(value)==canonical(expected),'MMC_T5_UNSUPPORTED_COMPLETION_CLAIM')
    return {'status':'SCOPED_CLAIMS_ONLY','evidence_strength':'SAME_AUTHOR_LOCAL_TESTS',**expected}
