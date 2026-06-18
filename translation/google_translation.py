import os
import json

# Import the Google Cloud Translation library.
from google.cloud import translate_v3

PROJECT_ID = "project-d82fc73e-ca8a-41d1-b54"


def translate_texts(texts: list[str] = "", source_language_code: str = "en", target_language_code: str = "fr", batch_size: int = 1024) -> list[str]:

    # Initialize Translation client.
    client = translate_v3.TranslationServiceClient()
    parent = f"projects/{PROJECT_ID}/locations/global"

    # https://cloud.google.com/translate/docs/supported-formats
    mime_type = "text/plain"  # MIME type of the content to translate.

    translations = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.translate_text(contents=batch, parent=parent, mime_type=mime_type, source_language_code=source_language_code, target_language_code=target_language_code)
        translations += [t.translated_text for t in response.translations]

    return translations


if __name__ == "__main__":
    with open("../gloss.json", "r", encoding="utf-8") as file_obj:
        gloss_list: dict = json.load(file_obj)

    en_glosses = [gloss["gloss_en"] for char, gloss in gloss_list.items()][:]
    fr_glosses = translate_texts(en_glosses)

    merged = {}
    for (char, gloss), fr_gloss in zip(gloss_list.items(), fr_glosses):
        merged[char] = {"gloss_en": gloss["gloss_en"], "gloss_fr": fr_gloss}

    out_dir = "google_translation"
    os.makedirs(out_dir, exist_ok=True)

    merged_path = os.path.join(out_dir, "gloss_translation.json")
    with open(merged_path, "w", encoding="utf-8") as f_out:
        json.dump(merged, f_out, ensure_ascii=False, indent=4)
