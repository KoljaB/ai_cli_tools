debug = False

import asyncio
import websockets
import json
import httpx
from typing import Dict, Any
import logging

if debug:
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
logger = logging.getLogger(__name__)

# Replace with your actual LMStudio server endpoint
LMSTUDIO_SERVER_URL = "http://localhost:1234/v1/chat/completions"

# Create a single httpx.AsyncClient to be reused
http_client = httpx.AsyncClient()

def log_detailed_error(e: Exception, context: str, extra_info: Dict[str, Any] = {}):
    """Log detailed error information including stacktrace."""
    logger.error(f"Error in {context}: {str(e)}")
    logger.error(f"Error type: {type(e).__name__}")
    for key, value in extra_info.items():
        logger.error(f"{key}: {value}")

async def handle_client(websocket, path):
    logger.info("WebSocket connection established")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)

                system_message = data.get("system", "")
                user_message = data.get("user", "")
                logger.info(f"Received system message: {system_message}")
                logger.info(f"Received user message: {user_message}")

                messages = []
                if system_message:
                    messages.append({"role": "system", "content": system_message})
                messages.append({"role": "user", "content": user_message})

                logger.info(f"Messages sent to LLM:\n{messages}")

                async with http_client.stream(
                    "POST",
                    LMSTUDIO_SERVER_URL,
                    json={
                        "messages": messages,
                        "stream": True,
                        "model": "local-model",
                        "temperature": 0.7
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=60.0
                ) as response:
                    if response.status_code != 200:
                        error_msg = f"Error contacting LMStudio server. Status code: {response.status_code}"
                        logger.error(error_msg)
                        await websocket.send(json.dumps({"error": error_msg}))
                        continue

                    async for line in response.aiter_lines():

                        if line.strip() == "data: [DONE]":
                            await websocket.send("")  # Send empty string to mark end of response
                            break
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])  # Skip "data: " prefix
                                if "choices" in data and len(data["choices"]) > 0:
                                    content = data["choices"][0]["delta"].get("content")
                                    if content:
                                        await websocket.send(content)
                                        logger.debug(f"Sent token: {content}")
                            except json.JSONDecodeError as json_error:
                                log_detailed_error(json_error, "JSON parsing", {"line": line})

            except json.JSONDecodeError:
                await websocket.send(json.dumps({"error": "Invalid JSON"}))
            except httpx.RequestError as request_error:
                log_detailed_error(request_error, "HTTP request to LMStudio")
                await websocket.send(json.dumps({"error": str(request_error)}))
            except Exception as e:
                log_detailed_error(e, "Processing request")
                await websocket.send(json.dumps({"error": str(e)}))

    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket disconnected")
    finally:
        logger.info("Closing WebSocket connection")

async def main_async():
    server = await websockets.serve(handle_client, "localhost", 5000)
    print("LLM Server started on ws://localhost:5000")
    await server.wait_closed()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()

