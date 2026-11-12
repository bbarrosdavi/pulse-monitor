"""Testes do protocolo serial e decodificação de amostras."""

from pulse_monitor.protocol import PpgSample, SourceMode, decode_sample, encode_sample


def test_encode_decode_roundtrip() -> None:
    sample = PpgSample(timestamp_ms=1250, ir_raw=99432, red_raw=84890, mode=SourceMode.VIRTUAL_ARDUINO)
    line = encode_sample(sample)
    assert line == "PPG,1250,99432,84890,2\n"
    decoded = decode_sample(line)
    assert decoded == sample


def test_decode_invalid_lines() -> None:
    assert decode_sample("") is None
    assert decode_sample("PONG,PULSE_MONITOR_V1,1\n") is None
    assert decode_sample("PPG,abc,100,200,1\n") is None
    assert decode_sample("PPG,10,100\n") is None
