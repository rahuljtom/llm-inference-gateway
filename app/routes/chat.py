from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from app.models.chat import ChatCompletionRequest
from app.providers.openai import OpenAIProvider

router = APIRouter(prefix="/v1", tags=["chat"])

def get_provider(model: str, request: Request):
    """
    Primitive routing based on model prefix. 
    V2 will load this from the database or dynamic config.
    """
    client = request.app.state.http_client
    if model.startswith("gpt-"):
        return OpenAIProvider(client=client)
    # Anthropic and Groq to be added in Phase 2
    raise HTTPException(status_code=400, detail=f"Unsupported model: {model}")

@router.post("/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    provider = get_provider(body.model, request)
    
    if body.stream:
        # SSE streams must be returned as StreamingResponse with text/event-stream
        return StreamingResponse(
            provider.stream(body),
            media_type="text/event-stream"
        )
    
    return await provider.complete(body)
