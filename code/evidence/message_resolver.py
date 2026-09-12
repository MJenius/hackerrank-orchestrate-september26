"""Extract bounded financial assertions; message instructions are never executed."""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MessageFact:
    message_id: str
    user_id: str
    fact_type: str
    amount: Optional[float] = None
    currency: Optional[str] = None
    effective_date: Optional[str] = None
    description: Optional[str] = None
    related_event_id: Optional[str] = None
    sent_at: str = ''
    details: dict = field(default_factory=dict)


class MessageResolver:
    @staticmethod
    def extract_facts(messages, user_id, request_date=None, request_id=None):
        facts = []
        for message in sorted(messages, key=lambda m: (m.sent_at, m.message_id)):
            if message.user_id != user_id:
                continue
            if request_date and message.sent_at[:10] > request_date:
                continue
            if request_id and message.request_id not in (None, request_id):
                continue
            text = message.message_text.lower()
            amounts = re.findall(r'\b(EUR|USD|IDR|INR|ZAR)\s*([\d,]+(?:\.\d+)?)', message.message_text, re.I)
            dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', text)
            kind, details = 'info', {}
            salary = message.source_type in ('employer', 'sms') and any(w in text for w in ('salary', 'gaji', 'monthly pay', 'employment', 'hubungan kerja', 'kontrak', 'contract'))
            if salary:
                if 'remaining confirmed monthly salary' in text or 'sisa gaji bulanan' in text:
                    kind = 'salary_remaining'
                elif 'contract has ended' in text or 'employment has ended' in text or ('berakhir' in text and ('kontrak' in text or 'hubungan kerja' in text)):
                    kind = 'salary_end'
                elif 'resumes' in text or ('gaji' in text and 'kembali' in text):
                    kind = 'salary_resume'
                elif 'first salary' in text or 'gaji pertama' in text:
                    kind = 'salary_start'
                elif 'now expected on' in text or 'diperkirakan masuk pada' in text:
                    kind = 'salary_delay'
                elif 'temporary monthly pay' in text or 'gaji bulanan sementara' in text:
                    kind = 'salary_temporary'
                elif ('salary' in text and 'reduced to' in text) or ('gaji' in text and 'dikurangi menjadi' in text):
                    kind = 'salary_next'
                elif 'increased to' in text or 'naik menjadi' in text:
                    kind = 'salary_increase'
                elif ('regular salary' in text or 'gaji rutin' in text) and amounts:
                    kind = 'salary_regular'
                    if len(amounts) > 1 and ('arrears' in text or 'tunggakan' in text):
                        details['one_time_amount'] = float(amounts[1][1].replace(',', ''))
                elif 'confirmed base salary' in text or 'gaji pokok' in text:
                    kind = 'salary_base'
                elif amounts and dates and ('confirmed' in text or 'dikonfirmasi' in text):
                    kind = 'salary_confirmed'
            elif message.source_type == 'service_provider' and ('client approved an invoice' in text or 'klien menyetujui pembayaran faktur' in text):
                kind = 'confirmed_invoice'
            elif message.source_type == 'service_provider' and any(w in text for w in (
                'can change', 'dapat berubah', "isn't withdrawable", 'isnt withdrawable',
                'not withdrawable', 'belum dapat ditarik', 'payout is still pending', 'masih tertunda'
            )):
                kind = 'income_uncertain'
            elif message.source_type in ('service_provider', 'merchant') and ('rent' in text or 'sewa' in text):
                pct = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
                if pct and any(w in text for w in ('increase', 'menaik', 'naik')):
                    kind, details = 'rent_increase', {'percentage': float(pct[1]) / 100}

            if message.related_event_id:
                if 'cancelled' in text or 'canceled' in text or 'dibatalkan' in text:
                    kind = 'event_cancel'
                elif 'previous debit attempt failed' in text or 'debit sebelumnya gagal' in text:
                    kind = 'event_retry'
                elif (('refund' in text or 'pengembalian dana' in text) and
                      any(w in text for w in ('not reached', 'still processing', 'belum masuk'))):
                    kind = 'credit_pending'
                elif any(w in text for w in ('has settled', 'have settled', 'have reached your account', 'sudah masuk ke rekening')):
                    kind = 'event_settled'

            facts.append(MessageFact(
                message.message_id, message.user_id, kind,
                float(amounts[0][1].replace(',', '')) if amounts else None,
                amounts[0][0].upper() if amounts else None,
                dates[0] if dates else None, message.message_text,
                message.related_event_id, message.sent_at, details,
            ))
        return facts
