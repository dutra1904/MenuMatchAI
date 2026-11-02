"""Erros de domínio traduzidos para a API."""


class DishNotFound(LookupError):
    def __init__(self, dish_id: str) -> None:
        self.dish_id = dish_id
        super().__init__(dish_id)


class RestaurantMismatch(ValueError):
    def __init__(self) -> None:
        super().__init__("Os pratos precisam ser do mesmo restaurante.")
