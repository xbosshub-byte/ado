import uasyncio as asyncio
from uado import Client 

def on_message_received(topic, payload):
    print(f"📥 ข้อความเข้า! Topic: {topic} | Data: {payload}")

async def main():
    # กำหนด IP ไปที่เซิร์ฟเวอร์ของคุณ
    client = Client(host='141.98.19.190', port=8666)
    client.on_message = on_message_received
    
    print("⏳ กำลังเชื่อมต่อไปยังเซิร์ฟเวอร์...")
    await client.connect()
    
    counter = 1
    while True:
        # ทดสอบส่งข้อมูลจาก ESP32 ทุกๆ 3 วินาที
        payload = {"status": "online", "device": "ESP32_01", "sensor_val": counter}
        await client.send("esp32/status", payload)
        print(f"📤 ส่งข้อมูลสำเร็จ: {payload}")
        
        counter += 1
        await asyncio.sleep(3)

if __name__ == '__main__':
    # หมายเหตุ: อย่าลืมเขียนโค้ดเชื่อมต่อ WiFi ให้เรียบร้อยก่อนเรียกใช้ฟังก์ชันนี้นะครับ
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔴 ปิดระบบ ESP32 Client")

