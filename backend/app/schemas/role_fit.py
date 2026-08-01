from pydantic import BaseModel


class RoleFitResult(BaseModel):
    role: str
    rating: int  # 1-5
    rationale: str = ""


class RoleFitLLMOutput(BaseModel):
    role_fit: list[RoleFitResult] = []