from typing import List, Union, Dict
from typing_extensions import TypedDict


class Images(TypedDict):
    img_url: str


class Buttons(TypedDict):
    type: str
    title: str
    value: str


class NLSQLAnswer(TypedDict):
    answer: str
    answer_type: str
    unaccounted: Union[str, None]
    addition_buttons: Union[List[Buttons], None]
    buttons:  Union[List[Buttons], None]
    images: Union[List[Images], None]
    card_data: Union[Dict, None]
