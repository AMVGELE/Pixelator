class PixelatorError(Exception):
    """Base class for user-facing Pixelator errors."""


class ConfigError(PixelatorError):
    """Raised when configuration cannot be loaded or validated."""


class VideoError(PixelatorError):
    """Raised when video probing, decoding, encoding, or muxing fails."""


class OutputError(PixelatorError):
    """Raised when output paths are invalid or unsafe."""
