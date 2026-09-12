"""Verified transcriptions of participant PNGs, never request decision labels.

Codex visually inspected all 16 supplied images on 2026-09-12. Descriptions name
the visible amount field; dates preserve printed text (blank if absent). The
currency comes from explicit text/symbols and the linked participant event.
Do not use receipt dates or due dates to overwrite an event's settlement date.
No OCR/API/model runs occur here; interactive inspection token counts are not
available from this cache and must not be fabricated in runtime usage reports.
"""
from dataclasses import dataclass, replace
from datetime import date
from hashlib import sha256
from pathlib import Path
import re
from typing import Optional


@dataclass(frozen=True)
class ImageFact:
    image_id: str
    amount: float
    currency: str
    description: str
    date: str  # Printed date text, not an inferred settlement date.
    source_type: str
    source_sha256: str
    amount_due_after_date: Optional[str] = None
    amount_due_after: Optional[float] = None


# ponytail: only these visually verified PNGs are supported; inspect and hash
# new/changed images before extending this transcription cache.
GROUNDED_IMAGE_FACTS = {
    'image_01': ImageFact('image_01', 4365000.0, 'IDR', 'Payslip Net Pay / transferred amount', 'Aug-2019', 'payslip', 'f37b40e6af42c664846057252cac89ad41b7d029dfe8dacff2db8cceb79fa5ba'),
    'image_02': ImageFact('image_02', 100000.0, 'INR', 'Rent receipt Balance Due; excludes amount already received', '11/08/23', 'receipt', 'ccd779e5382b1bcfacfb47d4ccf346ffd667a34c8b94d0cfd48aa4a609bd117d'),
    'image_03': ImageFact('image_03', 41272.0, 'INR', 'Riddhi Siddhi Net Amount / Cash Paid', '27/02/2026', 'receipt', 'e5fb0bbcda6cc06f8ea95e32e45d4c76acd8c594f4b02ff0d78e6006e103ee4d'),
    'image_04': ImageFact('image_04', 2854.0, 'INR', 'Delivered grocery order Item Bill', '', 'receipt', '281e7f1e7bd1f98fbd53cde1381977373e610e6634b11c98098000001ff10f0c'),
    'image_05': ImageFact('image_05', 704.05, 'INR', 'Airtel Amount due till 06-Feb-2026; 822.05 after that date', '06-Feb-2026', 'bill', '9abcda5647afb3dcdf91613253ac0160bd722333af33a4b952dfc96fea6ff97b', '2026-02-06', 822.05),
    'image_06': ImageFact('image_06', 1995.0, 'INR', 'Blink Commerce Total including delivery charges and tax', '', 'invoice', '9055551fbe5940feb01b947e1f18ccfed093192d103b1e930a56df0ea7cd3cb4'),
    'image_07': ImageFact('image_07', 8528.0, 'INR', 'Nagarjuna paid Grand Total (RS), rounded from 8528.10', '29-10-2025', 'invoice', 'f6d30a74355224c0b5cda2d7f96399a7b1a0afe4f9fe59ea048bbecb1a21311e'),
    'image_08': ImageFact('image_08', 15339.0, 'INR', 'Maintenance receipt Total Amount Received; original due date 30-08-2026 is not a new payment', '24-07-2026', 'receipt', 'e28592ad8b4dacd03055e0b1ebc46670c83fbfa1162af07bdef33bb226bf63c8'),
    'image_09': ImageFact('image_09', 723.0, 'INR', 'Water receipt Total Amount Received; original due date 02-07-2026 is not a new payment', '07-06-2026', 'receipt', 'e0e74e14425d923ff8a5c6db26ec6f4f26ee4697bfd257e414ba05c947a75ba8'),
    'image_10': ImageFact('image_10', 79679.26, 'INR', 'Grocery tax invoice Balance Due including taxes', '', 'invoice', 'c90f98caf0877083e471fd47dace772f83d4782037cf112e97c63f79a10ea8cf'),
    'image_11': ImageFact('image_11', 3650.0, 'INR', 'Jeevan Hospital Amount Payable / Balance; Amount Paid 0', '19-Jan-2023', 'invoice', '795e000d48428c97748e8af370cb02b604bec88cc52ec8930f38dc744624e886'),
    'image_12': ImageFact('image_12', 33.50, 'USD', 'CityCab Total; cash 40 minus change 6.50', '01/10/2025', 'receipt', 'e10b0123e66d512d82f6c431fb741053b336627b89b9d9a138071ac6980a14ff'),
    'image_13': ImageFact('image_13', 2298.0, 'INR', 'DailyObjects Total paid including taxes and delivery', '', 'receipt', '1ae54b378a9556d94b753093ba80e7117caf86fab4d3fe11ec84e3dd2f6d6dd8'),
    'image_14': ImageFact('image_14', 4543.0, 'INR', 'Pharmacy handwritten TOTAL; 1500+724+796+550+303+670', '', 'receipt', 'bf88e4aa35e6f36304cbf76bf6f505f32b04466bfd5f7df693fcb3ebe8a3e2c1'),
    'image_15': ImageFact('image_15', 9968.0, 'INR', 'InterGlobe Aviation Grand Total including taxes', '07-Jun-2026', 'invoice', '0c0fe3d79e670f2b423bbb2aafc0b5601d3eb4e659ac64058cd189abf7792ee1'),
    'image_16': ImageFact('image_16', 393.22, 'INR', 'Charging Total including CGST and SGST; payment method WALLET', '03/09/2026, 12:35:10 am', 'invoice', '2665cf731a861ddb217be5b8082fbd390850a7a98feec018519b6fda0b30b4f8'),
}


class ImageEvidenceExtractor:
    def __init__(self, media_dir: str = 'dataset/media/images'):
        self.media_dir = Path(media_dir)

    def extract_fact(self, image_id: str, settlement_date: Optional[str] = None) -> ImageFact:
        if not re.fullmatch(r'image_\d+', image_id):
            raise ValueError(f'Invalid image ID: {image_id!r}')
        image_path = self.media_dir / f'{image_id}.png'
        if not image_path.is_file():
            raise FileNotFoundError(f'Missing image evidence: {image_path}')
        fact = GROUNDED_IMAGE_FACTS.get(image_id)
        if fact is None:
            raise ValueError(f'No verified extraction for {image_id}; inspect the supplied image first')
        if sha256(image_path.read_bytes()).hexdigest() != fact.source_sha256:
            raise ValueError(f'Image evidence changed for {image_id}; inspect it before updating the cache')
        if settlement_date is not None:
            date.fromisoformat(settlement_date)
        if fact.amount_due_after_date:
            if settlement_date is None:
                raise ValueError(f'Settlement date required for dated amounts in {image_id}')
            if settlement_date > fact.amount_due_after_date:
                return replace(fact, amount=fact.amount_due_after)
        return fact
