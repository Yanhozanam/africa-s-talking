from lnd_client import (
    get_balance, create_invoice, send_payment,
    get_transactions, decode_invoice, sats_to_bif, bif_to_sats
)
from canal_store import (
    create_bif_canal, match_btc_canal,
    get_open_canals, get_canal, complete_canal
)

def CON(text): return f"CON {text}"
def END(text): return f"END {text}"

async def handle_ussd(session_id: str, phone: str, text: str) -> str:
    parts = [p.strip() for p in text.split("*")] if text.strip() else []

    if not parts:
        return CON(
            "KAZA KURI B_CASH\n"
            "Bitcoin y'Iwacu\n\n"
            "1. Ubutunzi (Balance)\n"
            "2. Kurunguka (Send)\n"
            "3. Kwakira (Receive)\n"
            "4. Kahise k'ikonti (History)\n"
            "5. Kuvunjisha (Exchange)"
        )

    level1 = parts[0]

    # 1. BALANCE
    if level1 == "1":
        data = await get_balance()
        if "error" in data:
            return END("Ikosa: LND ntibashije.\nGerageza kongera.")
        wallet = data.get("wallet_balance", {})
        channel = data.get("channel_balance", {})
        on_chain = wallet.get("confirmed_balance", 0)
        lightning = channel.get("balance", 0)
        total = on_chain + lightning
        bif = sats_to_bif(total)
        return END(
            f"Ubutunzi bwanyu ni:\n"
            f"Lightning: {lightning:,} sats\n"
            f"On-chain: {on_chain:,} sats\n"
            f"Total: {total:,} sats\n"
            f"= {bif:,} BIF"
        )

    # 2. SEND
    if level1 == "2":
        if len(parts) == 1:
            return CON("Ohereza BTC\n\nShyiramo invoice\nya Lightning:")
        if len(parts) == 2:
            invoice_str = parts[1]
            decoded = await decode_invoice(invoice_str)
            if "error" in decoded or "detail" in decoded:
                return END("Habaye akabazo.\nGerageza Hamyuma.")
            sats = int(decoded.get("num_satoshis", 0))
            bif_val = sats_to_bif(sats)
            return CON(
                f"Emeza:\n"
                f"{sats:,} sats\n"
                f"= {bif_val:,} BIF\n\n"
                f"1. Emeza\n"
                f"2. Reka"
            )
        if len(parts) == 3:
            if parts[2] == "1":
                invoice_str = parts[1]
                result = await send_payment(invoice_str)
                if result.get("payment_error") or "error" in result:
                    return END("Kurungika vyanse.\nMuragerageza hanyuma.")
                decoded = await decode_invoice(invoice_str)
                sats = int(decoded.get("num_satoshis", 0))
                bif_val = sats_to_bif(sats)
                return END(
                    f"Muhejeje kurungika\n"
                    f"{sats:,} sats\n"
                    f"= {bif_val:,} BIF"
                )
            return END("Gusubira Inyuma.")

    # 3. RECEIVE
    if level1 == "3":
        if len(parts) == 1:
            return CON("Kwakira BTC\n\nZingana na sats\n(urugero: 5000):")
        if len(parts) == 2:
            try:
                amount = int(parts[1])
            except ValueError:
                return END("Injiza igitigiri.\nUrugero: 5000")
            bif_val = sats_to_bif(amount)
            result = await create_invoice(amount, memo=f"B_CASH {phone}")
            if "error" in result:
                return END("Habaye akabazo.\nMuragerageza Hanyuma.")
            payment_req = result.get("payment_request", "")
            short = payment_req[:25] + "..."
            return END(
                f"Invoice\n"
                f"{amount:,} sats = {bif_val:,} BIF\n\n"
                f"{short}\n\n"
                f"Reba dashboard\n"
                f"invoice yuzuye."
            )

    # 4. HISTORY
    if level1 == "4":
        from main import lnd
        lines = ["Kahise k'ikonti:\n"]
        count = 0
        try:
            payments_resp = lnd.list_payments(max_payments=10)
            for p in reversed(payments_resp.payments):
                if count >= 3:
                    break
                sats = int(p.value)
                if sats > 0:
                    bif_val = sats_to_bif(sats)
                    lines.append(f"OUT {sats:,}s ~{bif_val:,}F")
                    count += 1
        except:
            pass
        try:
            invoices_resp = lnd.list_invoices(num_max_invoices=10)
            for inv in reversed(invoices_resp.invoices):
                if count >= 5:
                    break
                if inv.settled:
                    sats = int(inv.value)
                    bif_val = sats_to_bif(sats)
                    lines.append(f"IN  {sats:,}s ~{bif_val:,}F")
                    count += 1
        except:
            pass
        if count == 0:
            return END("Nta mateka arabonetse\nkuri konti yawe.")
        return END("\n".join(lines))

    # 5. EXCHANGE
    if level1 == "5":
        if len(parts) == 1:
            return CON(
                "Kuvunjisha\n\n"
                "1. BIF -> BTC\n"
                "2. BTC -> BIF"
            )
        level2 = parts[1]

        # 5.1 BIF -> BTC
        if level2 == "1":
            if len(parts) == 2:
                return CON("BIF -> BTC\n\nIngano mu BIF\n(urugero: 50000):")
            if len(parts) == 3:
                try:
                    bif_amount = int(parts[2])
                except ValueError:
                    return END("Injiza umubare.\nUrugero: 50000")
                sats = bif_to_sats(bif_amount)
                return CON(
                    f"Emeza canal:\n"
                    f"{bif_amount:,} BIF\n"
                    f"= {sats:,} sats\n\n"
                    f"1. Ugurura Canal\n"
                    f"2. Gusubira Inyuma"
                )
            if len(parts) == 4:
                if parts[3] == "1":
                    bif_amount = int(parts[2])
                    sats = bif_to_sats(bif_amount)
                    canal_id = create_bif_canal(phone, bif_amount, sats)
                    return END(
                        f"Canal Yuguruwe!\n"
                        f"ID: {canal_id}\n"
                        f"{bif_amount:,} BIF -> {sats:,} sats\n\n"
                        f"Rindira uwugura\n"
                        f"wo mu ruhande rwa BTC."
                    )
                return END("Gusubira Inyuma.")

        # 5.2 BTC -> BIF
        if level2 == "2":
            if len(parts) == 2:
                open_canals = get_open_canals()
                if not open_canals:
                    return END("Nta canal Yuguruye.\nGerageza hanyuma.")
                lines = ["Canals zifunguye:\n"]
                for i, c in enumerate(open_canals[:3], 1):
                    bif = c["bif_side"]["bif_amount"]
                    sats = c["sats_amount"]
                    lines.append(f"{i}. {c['canal_id']} ({bif:,}F={sats:,}s)")
                lines.append("\nShyiramwo ID ya canal:")
                return CON("\n".join(lines))
            if len(parts) == 3:
                canal_id = parts[2].strip().upper()
                canal = get_canal(canal_id)
                if not canal or canal["status"] != "WAITING_BTC":
                    return END(f"Canal {canal_id}\nIki gikogwa ntigishoboka.")
                sats = canal["sats_amount"]
                bif = canal["bif_side"]["bif_amount"]
                return CON(
                    f"Canal {canal_id}:\n"
                    f"{sats:,} sats -> {bif:,} BIF\n\n"
                    f"1. Emeza\n"
                    f"2. Subira Inyuma"
                )
            if len(parts) == 4:
                if parts[3] == "1":
                    canal_id = parts[2].strip().upper()
                    canal = get_canal(canal_id)
                    if not canal or canal["status"] != "WAITING_BTC":
                        return END("Canal yamaze gufatwa.")
                    sats = canal["sats_amount"]
                    bif = canal["bif_side"]["bif_amount"]
                    result = await create_invoice(sats, memo=f"B_CASH canal {canal_id}")
                    if "error" in result:
                        return END("Igikogwa ntigikunze.\nGerageza hanyuma.")
                    invoice = result.get("payment_request", "")
                    short = invoice[:25] + "..."
                    match_btc_canal(phone, canal_id, invoice)
                    complete_canal(canal_id)
                    return END(
                        f"Ishura invoice:\n"
                        f"{short}\n\n"
                        f"Warose: {bif:,} BIF\n"
                        f"Reba dashboard\n"
                        f"invoice yuzuye."
                    )
                return END("Gusubira Inyuma.")

    return END("Hitamo ntiyumvikana.\nDial *384*B_CASH# kongera.")