from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UiTokens:
    name: str
    scale: float
    page_title: int
    title: int
    detail_title: int
    section_title: int
    card_title: int
    row_title: int
    body: int
    small: int
    tiny: int
    mono: int
    mono_small: int
    button_height: int
    compact_button_height: int
    toolbar_button_height: int
    row_pad_y: int
    section_pad_y: int
    compact_name_len: int
    detail_wrap: int
    panel_wrap: int


def ui_tokens_for_size(size_name: str) -> UiTokens:
    size = (size_name or "default").strip().lower()
    if size == "compact":
        return UiTokens(
            name="compact",
            scale=0.94,
            page_title=18,
            title=17,
            detail_title=15,
            section_title=13,
            card_title=12,
            row_title=11,
            body=11,
            small=10,
            tiny=9,
            mono=10,
            mono_small=9,
            button_height=28,
            compact_button_height=24,
            toolbar_button_height=26,
            row_pad_y=0,
            section_pad_y=6,
            compact_name_len=28,
            detail_wrap=820,
            panel_wrap=430,
        )
    if size == "large":
        return UiTokens(
            name="large",
            scale=1.08,
            page_title=22,
            title=20,
            detail_title=18,
            section_title=16,
            card_title=14,
            row_title=13,
            body=13,
            small=12,
            tiny=11,
            mono=12,
            mono_small=11,
            button_height=36,
            compact_button_height=30,
            toolbar_button_height=34,
            row_pad_y=3,
            section_pad_y=10,
            compact_name_len=40,
            detail_wrap=980,
            panel_wrap=560,
        )
    return UiTokens(
        name="default",
        scale=1.0,
        page_title=20,
        title=18,
        detail_title=16,
        section_title=14,
        card_title=13,
        row_title=12,
        body=12,
        small=11,
        tiny=10,
        mono=11,
        mono_small=10,
        button_height=32,
        compact_button_height=26,
        toolbar_button_height=30,
        row_pad_y=1,
        section_pad_y=8,
        compact_name_len=34,
        detail_wrap=900,
        panel_wrap=500,
    )
