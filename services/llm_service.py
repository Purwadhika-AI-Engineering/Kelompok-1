"""
Lapisan koneksi ke OpenAI Chat Completion API.
Menyediakan fungsi pemanggilan LLM dengan dan tanpa structured output,
dipakai oleh Supervisor, Insight Agent, sql_tool, dan rag_tool.
"""

from typing import Type, TypeVar, cast

from langchain_openai import ChatOpenAI
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)

# Cache instance ChatOpenAI per nama model agar tidak dibuat ulang setiap pemanggilan.
_model_cache: dict[str, ChatOpenAI] = {}


def get_llm(model_name: str) -> ChatOpenAI:
    """Mengembalikan instance ChatOpenAI untuk nama model tertentu.
    
    Instance di-cache agar tidak membuat objek baru setiap pemanggilan,
    karena ChatOpenAI aman dipakai ulang lintas request.

    Args:
        model_name: Nama model OpenAI, contoh: gpt-5.4 atau gpt-5.4-mini.
    
    Returns:
        Instance ChatOpenAI yang siap dipanggil.
    """
    if model_name not in _model_cache:
        _model_cache[model_name] = ChatOpenAI(model=model_name)
        
    return _model_cache[model_name]


def call_structured(model_name: str, system_prompt: str, user_message: str, output_schema: Type[T]) -> T:
    """Memanggil LLM dan mengembalikan output sesuai schema Pydantic.
    
    Args:
        model_name: Nama model OpenAI yang dipanggil.
        system_prompt: Instruksi sistem untuk LLM.
        user_message: Pesan atau konteks investigasi yang dikirim ke LLM.
        output_schema: Class Pydantic yang menentukan struktur output yang diharapkan.

    Returns:
        Instance output_schema yang sudah divalidasi sesuai isi respons LLM.
    """
    llm = get_llm(model_name)

    # Membungkus LLM agar output dipaksa sesuai schema Pydantic, bukan teks bebas.
    structured_llm = llm.with_structured_output(
    output_schema,
    method="function_calling",
    strict=True,
    )
    result = structured_llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ])

    return cast(T, result)


def call_text(model_name: str, system_prompt: str, user_message: str) -> str:
    """Memanggil LLM dan mengembalikan output sebagai teks bebas.
    
    Dipakai untuk Insight Agent yang outputnya berupa narasi adaptif,
    bukan struktur Pydantic tetap.

    Args:
        model_name: Nama model OpenAI yang dipanggil.
        system_prompt: Instruksi sistem untuk LLM.
        user_message: Pesan atau konteks investigasi yang dikirim ke LLM.

    Returns:
        Teks respons LLM.
    """
    llm = get_llm(model_name)
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ])

    return str(response.content)
