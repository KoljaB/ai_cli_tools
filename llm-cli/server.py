from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect
import httpx
import json
import logging
import traceback
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Replace with your actual LMStudio server endpoint
LMSTUDIO_SERVER_URL = "http://localhost:1234/v1/chat/completions"

def log_detailed_error(e: Exception, context: str, extra_info: Dict[str, Any] = {}):
    """Log detailed error information including stacktrace."""
    logger.error(f"Error in {context}: {str(e)}")
    logger.error(f"Error type: {type(e).__name__}")
    logger.error(f"Stacktrace:\n{''.join(traceback.format_tb(e.__traceback__))}")
    for key, value in extra_info.items():
        logger.error(f"{key}: {value}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    async with httpx.AsyncClient() as client:
        try:
            while True:
                input_text = await websocket.receive_text()
                logger.info(f"Received input: {input_text}")

                try:
                    async with client.stream(
                        "POST",
                        LMSTUDIO_SERVER_URL,
                        json={
                            "messages": [{"role": "user", "content": input_text}],
                            "stream": True,
                            "model": "local-model",  # Adjust if needed
                            "temperature": 0.7
                        },
                        headers={"Content-Type": "application/json"},
                        timeout=60.0
                    ) as response:
                        if response.status_code != 200:
                            error_msg = f"Error contacting LMStudio server. Status code: {response.status_code}"
                            logger.error(error_msg)
                            await websocket.send_text(json.dumps({"error": error_msg}))
                            continue

                        async for line in response.aiter_lines():
                            if line.strip() == "data: [DONE]":
                                await websocket.send_text("")  # Send empty string to mark end of response
                                break
                            if line.startswith("data: "):
                                try:
                                    data = json.loads(line[6:])  # Skip "data: " prefix
                                    if "choices" in data and len(data["choices"]) > 0:
                                        content = data["choices"][0]["delta"].get("content")
                                        if content:
                                            await websocket.send_text(content)
                                            logger.debug(f"Sent token: {content}")
                                except json.JSONDecodeError as json_error:
                                    log_detailed_error(json_error, "JSON parsing", {"line": line})

                except httpx.RequestError as request_error:
                    log_detailed_error(request_error, "HTTP request to LMStudio")
                    await websocket.send_text(json.dumps({"error": str(request_error)}))
                except Exception as e:
                    log_detailed_error(e, "Processing request")
                    await websocket.send_text(json.dumps({"error": str(e)}))

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            log_detailed_error(e, "WebSocket connection")
        finally:
            logger.info("Closing WebSocket connection")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)


# from fastapi import FastAPI, WebSocket
# from starlette.websockets import WebSocketDisconnect
# import httpx
# import asyncio
# import json
# import logging

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# app = FastAPI()

# # Replace with your actual Ollama server endpoint
# OLLAMA_SERVER_URL = "http://localhost:11434/api/generate"

# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     async with httpx.AsyncClient() as client:

#         try:
#             while True:
#                 input_text = await websocket.receive_text()
#                 print(f"Received input: {input_text}")

#                 try:
#                     response = await client.post(
#                         OLLAMA_SERVER_URL,
#                         json={"model": "llama3.1:8b-instruct-fp16", "prompt": input_text, "stream": True}
#                     )

#                     if response.status_code != 200:
#                         await websocket.send_text(json.dumps({"error": "Error contacting Ollama server"}))
#                         continue

#                     async for line in response.aiter_lines():
#                         if line:
#                             try:
#                                 data = json.loads(line)
#                                 if "response" in data:
#                                     await websocket.send_text(data["response"])
#                                 if data.get("done", False):
#                                     break
#                             except json.JSONDecodeError:
#                                 print(f"Failed to parse JSON: {line}")
#                 except Exception as e:
#                     print(f"Error processing request: {e}")
#                     await websocket.send_text(json.dumps({"error": str(e)}))

#         except WebSocketDisconnect:
#             print("WebSocket disconnected")
#         except Exception as e:
#             print(f"Unexpected error: {e}")
#         finally:
#             print("Closing WebSocket connection")        


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="127.0.0.1", port=5000)