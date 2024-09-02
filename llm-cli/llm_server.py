debug = True

import asyncio
import websockets
import json
import httpx
from typing import Dict, Any
import logging
import os

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

# Define endpoints for different providers
PROVIDER_ENDPOINTS = {
    "lmstudio": "http://localhost:1234/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",    
    "ollama": "http://localhost:11434/api/chat"  
}

# Define default models for providers
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20240620",
    "ollama": "llama3.1"
}

# Create a single httpx.AsyncClient to be reused
http_client = httpx.AsyncClient()

def log_detailed_error(e: Exception, context: str, extra_info: Dict[str, Any] = {}):
    """Log detailed error information including stacktrace."""
    logger.error(f"Error in {context}: {str(e)}")
    logger.error(f"Error type: {type(e).__name__}")
    for key, value in extra_info.items():
        logger.error(f"{key}: {value}")


async def handle_anthropic_stream(response, websocket):
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            data = line[6:].strip()  # Remove "data: " prefix and whitespace
            if data == "[DONE]":
                await websocket.send("")  # Send empty string to mark end of response
                break
            try:
                event_data = json.loads(data)
                event_type = event_data.get("type")

                if event_type == "content_block_delta":
                    delta = event_data.get("delta", {}).get("text", "")
                    if delta:
                        await websocket.send(delta)
                        logger.debug(f"Sent delta: {delta}")
                elif event_type == "message_delta":
                    stop_reason = event_data.get("delta", {}).get("stop_reason")
                    if stop_reason:
                        logger.info(f"Message stopped. Reason: {stop_reason}")
                elif event_type == "message_stop":
                    await websocket.send("")  # Send empty string to mark end of response
                    logger.info("Message stop event received")
                    break
                # You can add more event type handlers here if needed

            except json.JSONDecodeError as json_error:
                logger.error(f"Error parsing JSON: {json_error}")
                logger.error(f"Problematic data: {data}")
        elif line.startswith("event: "):
            event_type = line[7:].strip()  # Remove "event: " prefix and whitespace
            logger.debug(f"Received event: {event_type}")
        elif line.strip() == "":
            # Empty line, ignore
            pass
        else:
            logger.warning(f"Unexpected line in stream: {line}")

async def handle_openai_stream(response, websocket):
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            if line.strip() == "data: [DONE]":
                await websocket.send("")  # Send empty string to mark end of response
                break
            try:
                json_data = json.loads(line[6:])  # Remove "data: " prefix
                content = json_data['choices'][0]['delta'].get('content')
                if content:
                    await websocket.send(content)
                    logger.debug(f"Sent content: {content}")
            except json.JSONDecodeError as json_error:
                logger.error(f"Error parsing JSON: {json_error}")
                logger.error(f"Problematic line: {line}")

async def handle_lmstudio_stream(response, websocket):
    # LMStudio uses the same format as OpenAI
    await handle_openai_stream(response, websocket)

async def handle_ollama_stream(response, websocket):
    logger.debug("Starting to handle Ollama stream")
    async for line in response.aiter_lines():
        logger.debug(f"Received line from Ollama: {line}")
        try:
            json_data = json.loads(line)
            logger.debug(f"Parsed JSON data: {json_data}")
            
            if json_data.get('done'):
                logger.debug("Received 'done' signal from Ollama")
                await websocket.send("")  # Send empty string to mark end of response
                break
            
            content = json_data.get('message', {}).get('content', '')
            if content:
                logger.debug(f"Sending content to client: {content}")
                await websocket.send(content)
            else:
                logger.debug("No content in this chunk")
        except json.JSONDecodeError as json_error:
            logger.error(f"Error parsing JSON: {json_error}")
            logger.error(f"Problematic line: {line}")
        except Exception as e:
            logger.error(f"Unexpected error in handle_ollama_stream: {str(e)}")

    logger.debug("Finished handling Ollama stream")

async def handle_client(websocket, path):
    logger.info("WebSocket connection established")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)

                system_message = data.get("system", "")
                user_message = data.get("user", "")
                provider = data.get("provider", "lmstudio")
                model = data.get("model") or DEFAULT_MODELS.get(provider)
                
                logger.info(f"Received system message: {system_message}")
                logger.info(f"Received user message: {user_message}")
                logger.info(f"Using provider: {provider}")
                logger.info(f"Using model: {model}")

                messages = []
                if system_message:
                    messages.append({"role": "system", "content": system_message})
                messages.append({"role": "user", "content": user_message})

                logger.info(f"Messages sent to LLM:\n{messages}")

                endpoint = PROVIDER_ENDPOINTS.get(provider)
                if not endpoint:
                    error_msg = f"Invalid provider: {provider}"
                    logger.error(error_msg)
                    await websocket.send(json.dumps({"error": error_msg}))
                    continue

                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    # "max_tokens": 1024  #  might want to make this configurable
                }
                headers = {"Content-Type": "application/json"}

                if provider == "anthropic":
                    headers["X-API-Key"] = os.environ.get('ANTHROPIC_API_KEY')
                    headers["anthropic-version"] = "2023-06-01"
                elif provider == "openai":
                    headers["Authorization"] = f"Bearer {os.environ.get('OPENAI_API_KEY')}"
                elif provider == "lmstudio":
                    payload["model"] = "local-model"

                async with httpx.AsyncClient() as client:
                    async with client.stream(
                        "POST",
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=60.0
                    ) as response:
                        if response.status_code != 200:
                            error_content = await response.text()
                            error_msg = f"Error contacting {provider} server. Status code: {response.status_code}. Response: {error_content}"
                            logger.error(error_msg)
                            await websocket.send(json.dumps({"error": error_msg}))
                            continue

                        logger.debug(f"Received 200 OK response from {provider}")

                        if provider == "anthropic":
                            await handle_anthropic_stream(response, websocket)
                        elif provider == "openai":
                            await handle_openai_stream(response, websocket)
                        elif provider == "lmstudio":
                            await handle_lmstudio_stream(response, websocket)
                        elif provider == "ollama":
                            await handle_ollama_stream(response, websocket)
                        else:
                            error_msg = f"Unsupported provider: {provider}"
                            logger.error(error_msg)
                            await websocket.send(json.dumps({"error": error_msg}))

            except json.JSONDecodeError:
                await websocket.send(json.dumps({"error": "Invalid JSON"}))
            except httpx.RequestError as request_error:
                log_detailed_error(request_error, f"HTTP request to {provider}")
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

