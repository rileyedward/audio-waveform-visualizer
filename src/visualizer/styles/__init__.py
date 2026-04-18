from . import radial, bars, waveform, particles

STYLES = {
    "radial": radial.draw,
    "bars": bars.draw,
    "waveform": waveform.draw,
    "particles": particles.draw,
}

FEATURE_KINDS = {
    "radial": "bands",
    "bars": "bands",
    "waveform": "wave",
    "particles": "energy",
}
