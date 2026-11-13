# Formato JSON genérico de importación

Sirve para importar manos desde cualquier origen (otro historial, un adaptador OCR propio, una grabación transcrita a mano).

```json
{
  "hands": [
    {
      "hand_id": "1",
      "source": "mi-herramienta",
      "hero": "Yo",
      "small_blind": 10,
      "big_blind": 20,
      "ante": 0,
      "button_seat": 1,
      "payouts": [1.0],
      "players": [
        {"name": "Yo", "seat": 1, "stack": 500, "hole_cards": ["Ah", "Kd"]},
        {"name": "Rival1", "seat": 2, "stack": 500},
        {"name": "Rival2", "seat": 3, "stack": 500, "hole_cards": ["Qs", "Qd"]}
      ],
      "actions": [
        {"street": "preflop", "player": "Rival1", "action": "post_sb", "amount": 10},
        {"street": "preflop", "player": "Rival2", "action": "post_bb", "amount": 20},
        {"street": "preflop", "player": "Yo", "action": "raise", "amount": 50},
        {"street": "preflop", "player": "Rival1", "action": "fold"},
        {"street": "preflop", "player": "Rival2", "action": "call", "amount": 30},
        {"street": "flop", "player": "Rival2", "action": "check"},
        {"street": "flop", "player": "Yo", "action": "bet", "amount": 60},
        {"street": "flop", "player": "Rival2", "action": "raise", "amount": 450, "all_in": true},
        {"street": "flop", "player": "Yo", "action": "fold"}
      ],
      "board": ["Qh", "7c", "2d"],
      "winners": ["Rival2"]
    }
  ]
}
```

Reglas:

- `street`: `preflop`, `flop`, `turn`, `river`.
- `action`: `post_sb`, `post_bb`, `post_ante`, `fold`, `check`, `call`, `bet`, `raise`.
- `amount`: para `bet`/`raise`, **cantidad total a la que se sube en esa calle**; para `call`, la cantidad pagada; para posts, lo puesto.
- Las cartas usan dos caracteres: rango `2-9 T J Q K A` y palo `s h d c`.
- `position` por jugador es opcional (`BTN`, `SB`, `BB`, `BTN/SB`); si falta se deduce de `button_seat`.
- Solo se analizan las manos en las que el héroe tiene `hole_cards`.

También se acepta una lista de manos directamente (`[ {...}, {...} ]`).
