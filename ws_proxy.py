import asyncio
import websockets
import sys

async def pipe_ws_to_tcp(ws, writer, port):
    try:
        async for message in ws:
            if isinstance(message, str):
                data = message.encode('utf-8')
            else:
                data = message
            print(f"[WS -> TCP:{port}] {data}", flush=True)
            writer.write(data)
            await writer.drain()
    except Exception as e:
        print(f"[-] WS read error ({port}): {e}", flush=True)
    finally:
        writer.close()

async def pipe_tcp_to_ws(reader, ws, port):
    try:
        while not reader.at_eof():
            data = await reader.read(4096)
            if not data:
                break
            print(f"[TCP:{port} -> WS] {data}", flush=True)
            await ws.send(data)
    except Exception as e:
        print(f"[-] TCP read error ({port}): {e}", flush=True)
    finally:
        await ws.close()

async def handle_client(ws, *args, target_port=6112):
    print(f"[+] New connection accepted -> Port: {target_port}", flush=True)
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', target_port)
    except Exception as e:
        print(f"[-] Could not connect to TCP server (127.0.0.1:{target_port}): {e}", flush=True)
        await ws.close()
        return

    await asyncio.gather(
        pipe_ws_to_tcp(ws, writer, target_port),
        pipe_tcp_to_ws(reader, ws, target_port)
    )
    print(f"[-] Connection closed -> Port: {target_port}", flush=True)

async def main():
    async with websockets.serve(lambda ws, *args: handle_client(ws, *args, target_port=6112), "0.0.0.0", 8080), \
               websockets.serve(lambda ws, *args: handle_client(ws, *args, target_port=9875), "0.0.0.0", 8081):
        print("[✓] Login WS Proxy 8080 -> TCP 6112 Ready", flush=True)
        print("[✓] World WS Proxy 8081 -> TCP 9875 Ready", flush=True)
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
