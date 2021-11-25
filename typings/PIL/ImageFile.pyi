"""
This type stub file was generated by pyright.
"""

from typing import Any, NoReturn

from .Image import Image

_T = ...
MAXBLOCK: int
SAFEBLOCK: Any
LOAD_TRUNCATED_IMAGES: bool
ERRORS: Any

def raise_oserror(error) -> NoReturn: ...
def raise_ioerror(error) -> NoReturn: ...

class ImageFile(Image):
    custom_mimetype: Any
    tile: Any
    readonly: int
    decoderconfig: Any
    decodermaxblock: Any
    fp: Any
    filename: Any
    def __init__(self, fp: Any | None = ..., filename: Any | None = ...) -> None: ...
    def get_format_mimetype(self): ...
    def verify(self) -> None: ...
    map: Any
    im: Any
    def load(self): ...
    def load_prepare(self) -> None: ...
    def load_end(self) -> None: ...

class StubImageFile(ImageFile):
    def load(self) -> None: ...

class Parser:
    incremental: Any | None
    image: Any | None
    data: Any | None
    decoder: Any | None
    offset: int
    finished: bool
    def reset(self) -> None: ...
    decode: Any
    def feed(self, data) -> None: ...
    def __enter__(self: _T) -> _T: ...
    def __exit__(self, *args: Any) -> None: ...
    def close(self) -> Image: ...

class PyCodecState:
    xsize: int
    ysize: int
    xoff: int
    yoff: int
    def extents(self) -> tuple[int, int, int, int]: ...

class PyDecoder:
    im: Any
    state: Any
    fd: Any
    mode: Any
    def __init__(self, mode, *args) -> None: ...
    args: Any
    def init(self, args) -> None: ...
    @property
    def pulls_fd(self): ...
    def decode(self, buffer) -> None: ...
    def cleanup(self) -> None: ...
    def setfd(self, fd) -> None: ...
    def setimage(self, im, extents: Any | None = ...) -> None: ...
    def set_as_raw(self, data, rawmode: Any | None = ...) -> None: ...