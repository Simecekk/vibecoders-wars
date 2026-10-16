"""Example area (maintainer). This is what an area looks like: its own APIRouter, nothing else."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_ITEMS: dict[int, str] = {1: "tiger"}


class Item(BaseModel):
    id: int
    name: str


@router.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int) -> Item:
    if item_id not in _ITEMS:
        raise HTTPException(status_code=404, detail="Item not found")
    return Item(id=item_id, name=_ITEMS[item_id])


@router.post("/echo")
def echo(item: Item) -> Item:
    return item
