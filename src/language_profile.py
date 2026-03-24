#!/usr/bin/env python3
"""
NAVI-Translate: 다국어 프로파일 관리 모듈
언어별 용어집, 문체, 검증 규칙을 통합 관리합니다.

사용법:
    from language_profile import load_profile, list_available_languages, build_translation_prompt

    profile = load_profile("de")   # 독일어 프로파일
    prompt = build_translation_prompt(profile, style="literary")
"""
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
LANGUAGES_DIR = PROJECT_ROOT / "config" / "languages"
LEGACY_GLOSSARY = PROJECT_ROOT / "config" / "glossary.json"


@dataclass
class LanguageProfile:
    """언어별 번역 프로파일"""
    code: str
    name: str
    name_en: str = ""
    source_name: str = ""
    target: str = "ko"

    # 용어집 (단순 문자열 또는 {translation, note, context} 확장 형식)
    glossary: dict = field(default_factory=dict)

    # 문체 옵션
    default_style: str = "natural"
    style_options: dict = field(default_factory=dict)
    register_detection: dict = field(default_factory=dict)

    # 번역 가이드라인
    translation_guidelines: list = field(default_factory=list)

    # 문화 노트
    cultural_notes: dict = field(default_factory=dict)

    # 검증 설정
    check_residual: bool = True
    source_script_pattern: str = ""
    source_script_name: str = ""
    allowed_residuals: list = field(default_factory=list)
    length_ratio_min: float = 0.3
    length_ratio_max: float = 2.0

    def get_style(self, style_key: str = None) -> str:
        """문체 설명 텍스트를 반환합니다."""
        key = style_key or self.default_style
        return self.style_options.get(key, self.style_options.get(self.default_style, ""))

    def get_glossary_text(self) -> str:
        """용어집을 프롬프트용 텍스트로 변환합니다."""
        lines = []
        for src, val in self.glossary.items():
            if isinstance(val, dict):
                trans = val.get("translation", "")
                note = val.get("note", "")
                line = f"- {src} → {trans}"
                if note:
                    line += f" ({note})"
                lines.append(line)
            else:
                lines.append(f"- {src} → {val}")
        return "\n".join(lines) if lines else "(용어집 없음)"

    def get_validation_pattern(self) -> Optional[re.Pattern]:
        """잔존 검증용 정규식 패턴을 컴파일하여 반환합니다."""
        if not self.check_residual or not self.source_script_pattern:
            return None
        try:
            return re.compile(self.source_script_pattern)
        except re.error:
            return None

    def is_allowed_residual(self, text: str) -> bool:
        """허용된 잔존 단어인지 확인합니다."""
        return text in self.allowed_residuals


def load_profile(lang_code: str) -> LanguageProfile:
    """
    언어 프로파일을 로드합니다.

    우선순위:
    1. config/languages/{lang_code}.json
    2. lang_code == "ja"이면 config/glossary.json 폴백
    """
    profile_path = LANGUAGES_DIR / f"{lang_code}.json"

    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _parse_profile(data)

    # ja 폴백: 기존 glossary.json 사용
    if lang_code == "ja" and LEGACY_GLOSSARY.exists():
        with open(LEGACY_GLOSSARY, "r", encoding="utf-8") as f:
            glossary = json.load(f)
        return LanguageProfile(
            code="ja",
            name="일본어",
            name_en="Japanese",
            source_name="日本語",
            glossary=glossary,
            default_style="hitori",
            style_options={
                "hitori": "사이토 히토리 문체, 따뜻한 대화체, 해요체 혼용",
                "natural": "자연스러운 한국어, 번역투 제거, 단문 위주",
            },
            check_residual=True,
            source_script_pattern=r"[\u3040-\u309F\u30A0-\u30FF\u31F0-\u31FF\uFF66-\uFF9F]+",
            source_script_name="히라가나/카타카나",
            translation_guidelines=[
                "100% 한국어만 출력 (일본어/중국어 절대 금지)",
                "번역투 제거: '~의' 남용 금지, 자연스러운 능동형",
                "극한의 단문: 복문을 2~3개 짧은 단문으로 분리",
            ],
        )

    raise FileNotFoundError(
        f"언어 프로파일을 찾을 수 없습니다: {lang_code}\n"
        f"  경로: {profile_path}\n"
        f"  사용 가능한 언어: {', '.join(c['code'] for c in list_available_languages())}"
    )


def _parse_profile(data: dict) -> LanguageProfile:
    """JSON 데이터를 LanguageProfile로 변환합니다."""
    lang = data.get("language", {})
    style = data.get("style", {})
    validation = data.get("validation", {})
    length_ratio = validation.get("length_ratio", {})

    return LanguageProfile(
        code=lang.get("code", ""),
        name=lang.get("name", ""),
        name_en=lang.get("name_en", ""),
        source_name=lang.get("source_name", ""),
        target=lang.get("target", "ko"),
        glossary=data.get("glossary", {}),
        default_style=style.get("default", "natural"),
        style_options=style.get("options", {}),
        register_detection=style.get("register_detection", {}),
        translation_guidelines=data.get("translation_guidelines", []),
        cultural_notes=data.get("cultural_notes", {}),
        check_residual=validation.get("check_residual", True),
        source_script_pattern=validation.get("source_script_pattern", ""),
        source_script_name=validation.get("source_script_name", ""),
        allowed_residuals=validation.get("allowed_residuals", []),
        length_ratio_min=length_ratio.get("min", 0.3),
        length_ratio_max=length_ratio.get("max", 2.0),
    )


def list_available_languages() -> list[dict]:
    """사용 가능한 언어 목록을 반환합니다."""
    languages = []

    if LANGUAGES_DIR.exists():
        for path in sorted(LANGUAGES_DIR.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                lang = data.get("language", {})
                languages.append({
                    "code": lang.get("code", path.stem),
                    "name": lang.get("name", path.stem),
                    "name_en": lang.get("name_en", ""),
                })
            except (json.JSONDecodeError, KeyError):
                languages.append({"code": path.stem, "name": path.stem, "name_en": ""})

    # 폴백: glossary.json이 있으면 ja 추가 (중복 방지)
    if not any(l["code"] == "ja" for l in languages) and LEGACY_GLOSSARY.exists():
        languages.insert(0, {"code": "ja", "name": "일본어", "name_en": "Japanese"})

    return languages


def build_translation_prompt(profile: LanguageProfile, style_key: str = None) -> str:
    """
    번역 프롬프트를 조합합니다.
    용어집 + 문체 + 가이드라인 + 문화 노트를 포함합니다.
    """
    style_desc = profile.get_style(style_key)
    glossary_text = profile.get_glossary_text()

    # 가이드라인
    guidelines = ""
    if profile.translation_guidelines:
        guidelines = "\n## 번역 가이드라인\n"
        guidelines += "\n".join(f"- {g}" for g in profile.translation_guidelines)

    # 문화 노트
    cultural = ""
    if profile.cultural_notes:
        cn = profile.cultural_notes
        parts = []
        if cn.get("guideline"):
            parts.append(f"- 기본 원칙: {cn['guideline']}")
        if cn.get("well_known"):
            parts.append(f"- 잘 알려진 용어 (원문 유지 가능): {', '.join(cn['well_known'])}")
        if cn.get("needs_explanation"):
            for term, desc in cn["needs_explanation"].items():
                parts.append(f"- {term}: {desc}")
        if parts:
            cultural = "\n## 문화적 맥락\n" + "\n".join(parts)

    # 레지스터 감지
    register = ""
    if profile.register_detection:
        reg_parts = []
        for key, desc in profile.register_detection.items():
            reg_parts.append(f"- {key}: {desc}")
        if reg_parts:
            register = "\n## 격식/존칭 규칙\n" + "\n".join(reg_parts)

    prompt = f"""당신은 {profile.name}→한국어 전문 번역가입니다.

## 역할
- 이미지에 있는 {profile.name} 텍스트를 읽고 한국어로 번역합니다

## 출력 규칙
- 100% 한국어(한글+숫자+기본부호)만 출력
- {profile.name} 원문 잔류 금지
- AI 메타 발화(인사, 설명, 완료 보고) 금지 — 번역 텍스트만 출력

## 용어집
{glossary_text}

## 문체
{style_desc}
{guidelines}
{cultural}
{register}"""

    return prompt.strip()


# CLI로 실행 시 프로파일 정보 출력
if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "ja"
    try:
        p = load_profile(code)
        print(f"=== {p.name} ({p.code}) ===")
        print(f"  용어집: {len(p.glossary)}항목")
        print(f"  기본 문체: {p.default_style}")
        print(f"  문체 옵션: {list(p.style_options.keys())}")
        print(f"  잔존 검증: {'활성' if p.check_residual else '비활성'}")
        print(f"  가이드라인: {len(p.translation_guidelines)}개")
        print(f"\n--- 번역 프롬프트 미리보기 ---")
        print(build_translation_prompt(p))
    except FileNotFoundError as e:
        print(f"오류: {e}")
