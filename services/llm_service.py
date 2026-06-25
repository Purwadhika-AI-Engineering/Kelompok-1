"""
Lapisan koneksi ke OpenAI Chat Completion API.
Menyediakan fungsi pemanggilan LLM dengan dan tanpa structured output,
dipakai oleh Supervisor, Insight Agent, sql_tool, dan rag_tool.
"""

from typing import Optional, Type, TypeVar, cast

from langchain_openai import ChatOpenAI
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)

# Cache instance ChatOpenAI per kombinasi model dan max_tokens.
_model_cache: dict[tuple, ChatOpenAI] = {}


def get_llm(model_name: str, max_tokens: Optional[int] = None) -> ChatOpenAI:
    """Mengembalikan instance ChatOpenAI untuk nama model dan max_tokens tertentu.

    Instance di-cache per kombinasi model_name dan max_tokens agar tidak
    membuat objek baru setiap pemanggilan.

    Args:
        model_name: Nama model OpenAI, contoh: gpt-5.4 atau gpt-5.4-mini.
        max_tokens: Batas maksimum token output, None berarti tidak dibatasi.

    Returns:
        Instance ChatOpenAI yang siap dipanggil.
    """
    cache_key = (model_name, max_tokens)
    if cache_key not in _model_cache:
        _model_cache[cache_key] = ChatOpenAI(
            model=model_name,
            max_tokens=max_tokens  # type: ignore
        )

    return _model_cache[cache_key]


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
    # call_structured tidak butuh max_tokens karena output dikontrol schema Pydantic.
    llm = get_llm(model_name)

    # Membungkus LLM agar output dipaksa sesuai schema Pydantic, bukan teks bebas.
    structured_llm = llm.with_structured_output(
        output_schema,
        method="function_calling"
    )
    result = structured_llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ])

    return cast(T, result)


def call_text(model_name: str, system_prompt: str, user_message: str, max_tokens: Optional[int] = None) -> str:
    """Memanggil LLM dan mengembalikan output sebagai teks bebas.

    Dipakai untuk Insight Agent yang outputnya berupa narasi adaptif,
    bukan struktur Pydantic tetap.

    Args:
        model_name: Nama model OpenAI yang dipanggil.
        system_prompt: Instruksi sistem untuk LLM.
        user_message: Pesan atau konteks investigasi yang dikirim ke LLM.
        max_tokens: Batas maksimum token output sebagai safety net, None berarti tidak dibatasi.

    Returns:
        Teks respons LLM.
    """
    llm = get_llm(model_name, max_tokens)
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ])

    return str(response.content)