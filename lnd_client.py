import os
import codecs
from dotenv import load_dotenv

load_dotenv()

# Read the exchange rate from .env
BTC_BIF_RATE = float(os.getenv("BTC_BIF_RATE", "11500000.0"))

def sats_to_bif(sats: int) -> int:
    return int(sats * BTC_BIF_RATE / 100_000_000)

def bif_to_sats(bif: int) -> int:
    return int(bif * 100_000_000 / BTC_BIF_RATE)

# --- Direct gRPC Safe Wrapper Functions ---
# Instead of spinning up an HTTP client, we import the live connection from main.py

async def get_balance() -> dict:
    from main import lnd
    try:
        wallet_balance = lnd.get_balance()
        channel_balance = lnd.get_channel_balance()
        return {
            "wallet_balance": {
                "total_balance": wallet_balance.total_balance,
                "confirmed_balance": wallet_balance.confirmed_balance,
                "unconfirmed_balance": wallet_balance.unconfirmed_balance
            },
            "channel_balance": {
                "balance": channel_balance.balance,
                "pending_open_balance": channel_balance.pending_open_balance
            }
        }
    except Exception as e:
        return {"error": str(e)}

async def create_invoice(amount_sats: int, memo: str = "") -> dict:
    from main import lnd
    try:
        response = lnd.create_invoice(amount=amount_sats, memo=memo, expiry=3600)
        return {
            "payment_request": response.payment_request,
            "r_hash": codecs.encode(response.r_hash, 'hex').decode(),
            "add_index": response.add_index
        }
    except Exception as e:
        return {"error": str(e)}

async def send_payment(payment_request: str) -> dict:
    from main import lnd
    try:
        response = lnd.send_payment(payment_request=payment_request)
        if response.payment_error:
            return {"error": response.payment_error}
        return {
            "payment_hash": codecs.encode(response.payment_hash, 'hex').decode(),
            "payment_preimage": codecs.encode(response.payment_preimage, 'hex').decode()
        }
    except Exception as e:
        return {"error": str(e)}

async def get_transactions() -> dict:
    from main import lnd
    try:
        payments_resp = lnd.list_payments(max_payments=50)
        result = []
        for payment in payments_resp.payments:
            result.append({
                "payment_hash": payment.payment_hash,
                "value": payment.value,
                "status": payment.status.name
            })
        return {"payments": result}
    except Exception as e:
        return {"error": str(e)}

async def decode_invoice(payment_request: str) -> dict:
    from main import lnd
    try:
        import lightning_pb2 as ln
        request = ln.PayReqString(pay_req=payment_request)
        response = lnd.stub.DecodePayReq(request, metadata=lnd._get_metadata())
        return {
            "num_satoshis": response.num_satoshis,
            "description": response.description,
            "expiry": response.expiry
        }
    except Exception as e:
        return {"error": str(e)}