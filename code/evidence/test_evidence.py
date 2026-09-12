"""Run with: python -m code.evidence.test_evidence"""
from dataclasses import FrozenInstanceError
from pathlib import Path
from tempfile import TemporaryDirectory

from code.evidence.image_extractor import GROUNDED_IMAGE_FACTS, ImageEvidenceExtractor


def check():
    media = Path(__file__).resolve().parents[2] / 'dataset' / 'media' / 'images'
    extractor = ImageEvidenceExtractor(media)
    for image_id, cached in GROUNDED_IMAGE_FACTS.items():
        assert extractor.extract_fact(image_id, '2026-02-06') == cached
    assert extractor.extract_fact('image_05', '2026-02-07').amount == 822.05
    assert extractor.extract_fact('image_05', '2026-02-06').amount == 704.05
    assert extractor.extract_fact('image_12').amount == 40 - 6.50
    try:
        extractor.extract_fact('image_05')
    except ValueError as exc:
        assert 'Settlement date required' in str(exc)
    else:
        raise AssertionError('Dated bill needs a settlement date')
    for image_id in ('../image_01', 'image_01/../../secret', '/image_01'):
        try:
            extractor.extract_fact(image_id)
        except ValueError:
            pass
        else:
            raise AssertionError('Image ID accepted a path')
    try:
        extractor.extract_fact('image_01').amount = 1
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError('Shared evidence was mutable')
    with TemporaryDirectory() as temp:
        temporary = ImageEvidenceExtractor(temp)
        try:
            temporary.extract_fact('image_01')
        except FileNotFoundError:
            pass
        else:
            raise AssertionError('Missing image reused cached facts')
        Path(temp, 'image_01.png').write_bytes((media / 'image_01.png').read_bytes())
        assert temporary.extract_fact('image_01').amount == 4365000
        Path(temp, 'image_01.png').write_bytes(b'changed image')
        Path(temp, 'image_99.png').write_bytes(b'new image')
        for image_id in ('image_01', 'image_99'):
            try:
                temporary.extract_fact(image_id)
            except ValueError:
                pass
            else:
                raise AssertionError('Unverified image produced a cached fact')
    print('Image evidence checks passed (16 verified PNGs, dates, missing/changed/unknown sources).')


if __name__ == '__main__':
    check()
