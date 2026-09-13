from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from data.models import UploadResponse
from data.parser import CSVPipelineError, MissingColumnsError
from data.pipeline import process_csv_bytes

app = FastAPI(title="Fitness Intelligence API")

# Development CORS: allow local Next.js dev server.
# Easy to extend later via environment variables if needed.
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)):
    """Accept a workout CSV (multipart form data) and run the Phase 2 pipeline.

    The file is processed in memory; nothing is persisted.
    """
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_file",
                "message": "A .csv file must be uploaded using multipart form data.",
            },
        )

    data = await file.read()
    try:
        return process_csv_bytes(data)
    except MissingColumnsError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_columns",
                "message": exc.message,
                "missing_columns": exc.missing,
            },
        ) from exc
    except CSVPipelineError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_csv", "message": exc.message},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "processing_error",
                "message": "The CSV could not be processed due to a server error.",
            },
        ) from exc
