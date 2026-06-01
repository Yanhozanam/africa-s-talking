from pyngrok import ngrok
import time

public_url = ngrok.connect(8000)
print(f"\n✅ Public URL: {public_url}")
print(f"✅ USSD Callback: {public_url}/ussd")
print("\nKeep this running while testing AT...")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    ngrok.disconnect(public_url)