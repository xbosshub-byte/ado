import asyncio
import json
import struct

class Broker:
    def __init__(self, host='0.0.0.0', port=8666):
        self.host = host
        self.port = port
        self.clients = set()

    async def handle_client(self, reader, writer):
        self.clients.add(writer)
        addr = writer.get_extra_info('peername')
        print(f"[ado Broker] 🟢 Connected: {addr}")
        
        try:
            while True:
                raw_msglen = await reader.readexactly(4)
                if not raw_msglen: break
                msglen = struct.unpack('>I', raw_msglen)[0]
                
                data = await reader.readexactly(msglen)
                message = json.loads(data.decode('utf-8'))
                
                # กระจายข้อความให้ทุกคนยกเว้นคนส่ง
                await self.broadcast(data, writer)
                
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass # Client ตัดการเชื่อมต่อปกติ
        except Exception as e:
            print(f"[ado Broker] ❌ Error ({addr}): {e}")
        finally:
            if writer in self.clients:
                self.clients.remove(writer)
            writer.close()
            await writer.wait_closed()
            print(f"[ado Broker] 🔴 Disconnected: {addr}")

    async def broadcast(self, raw_data, sender_writer):
        msglen = struct.pack('>I', len(raw_data))
        packet = msglen + raw_data
        
        disconnected = []
        for client in self.clients:
            if client != sender_writer:
                try:
                    client.write(packet)
                    await client.drain()
                except Exception:
                    # เก็บรายชื่อ Client ที่ส่งข้อมูลไม่ผ่าน (สายหลุด)
                    disconnected.append(client)
        
        # เคลียร์ Client ที่ตายแล้วออกจากระบบ
        for client in disconnected:
            if client in self.clients:
                self.clients.remove(client)

    async def start(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        print(f"[ado Broker] 🚀 Running on {self.host}:{self.port}")
        async with server:
            await server.serve_forever()


class Client:
    def __init__(self, host='127.0.0.1', port=8666):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.on_message = None # Callback function
        self._connected = False

    async def connect(self):
        # รันระบบจัดการการเชื่อมต่อ (และเชื่อมต่อใหม่) เป็น Background Task
        asyncio.create_task(self._connection_manager())
        # ป้องกันไม่ให้โค้ดหลักไปต่อ จนกว่าจะเชื่อมต่อสำเร็จครั้งแรก
        while not self._connected:
            await asyncio.sleep(0.1)

    async def _connection_manager(self):
        while True:
            try:
                if not self._connected:
                    self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
                    self._connected = True
                    print(f"[ado Client] 🟢 Connected to {self.host}:{self.port}")
                    
                    # เข้าสู่ Loop รอรับข้อความ
                    await self.listen()
            except Exception as e:
                if self._connected:
                    print(f"[ado Client] 🔴 Connection lost: {e}")
                self._connected = False
            
            # หากหลุดจาก Loop (เน็ตตัด/เซิร์ฟดับ) จะรอ 3 วินาทีแล้วลองเชื่อมต่อใหม่
            await asyncio.sleep(3)
            if not self._connected:
                print(f"[ado Client] ⏳ Reconnecting to {self.host}:{self.port}...")

    async def send(self, topic, payload):
        if not self._connected or not self.writer:
            print("[ado Client] ⚠️ Cannot send, not connected.")
            return False
            
        try:
            msg_dict = {"topic": topic, "payload": payload}
            data = json.dumps(msg_dict).encode('utf-8')
            msglen = struct.pack('>I', len(data))
            self.writer.write(msglen + data)
            await self.writer.drain()
            return True
        except Exception as e:
            print(f"[ado Client] ❌ Send error: {e}")
            self._connected = False # สั่งให้เข้าสู่โหมดเชื่อมต่อใหม่
            return False

    async def listen(self):
        try:
            while True:
                raw_msglen = await self.reader.readexactly(4)
                if not raw_msglen: break
                msglen = struct.unpack('>I', raw_msglen)[0]
                
                data = await self.reader.readexactly(msglen)
                message = json.loads(data.decode('utf-8'))
                
                if self.on_message:
                    self.on_message(message['topic'], message['payload'])
                    
        except (asyncio.IncompleteReadError, ConnectionResetError):
            print("[ado Client] 🔴 Disconnected from broker.")
        except Exception as e:
            print(f"[ado Client] ❌ Listen error: {e}")
        finally:
            self._connected = False
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()

