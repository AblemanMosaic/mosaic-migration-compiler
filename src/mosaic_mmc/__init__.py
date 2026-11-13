"""Mosaic Migration Compiler. Compilation is not authorization."""
from ._pins import VERSION as __version__
from .codec import canonical, decode, digest
from .model import validate_model
from .compiler import compile_model, verify_compilation
from .contracts import profile_reference, capabilities, program_inspect
from .errors import MMCError
__all__=['canonical','decode','digest','validate_model','compile_model','verify_compilation',
         'profile_reference','capabilities','program_inspect','MMCError']
