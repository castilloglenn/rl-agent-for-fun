from itertools import count
from typing import Any, Callable, TypeVar

C = TypeVar("C")
R = TypeVar("R")

System = Callable[["World"], None]


class World:
    """Holds entities, their components, per-world resources, and systems.

    Determinism rules (see docs/decisions/005-entity-component-system.md):
    systems run in the order they were added, and queries return entities
    in ascending ID order.
    """

    def __init__(self) -> None:
        self._ids = count(start=1)
        self._entities: dict[int, dict[type, Any]] = {}
        self._stores: dict[type, dict[int, Any]] = {}
        self._resources: dict[type, Any] = {}
        self._systems: list[System] = []

    # Entities

    def create_entity(self, *components: Any) -> int:
        entity = next(self._ids)
        self._entities[entity] = {}
        for component in components:
            self.add_component(entity, component)
        return entity

    def delete_entity(self, entity: int) -> None:
        for component_type in self._entities.pop(entity):
            del self._stores[component_type][entity]

    def entity_exists(self, entity: int) -> bool:
        return entity in self._entities

    # Components

    def add_component(self, entity: int, component: Any) -> None:
        component_type = type(component)
        self._entities[entity][component_type] = component
        self._stores.setdefault(component_type, {})[entity] = component

    def remove_component(self, entity: int, component_type: type[C]) -> C:
        del self._stores[component_type][entity]
        return self._entities[entity].pop(component_type)

    def component(self, entity: int, component_type: type[C]) -> C:
        return self._entities[entity][component_type]

    def try_component(
        self, entity: int, component_type: type[C]
    ) -> C | None:
        return self._entities[entity].get(component_type)

    def has_components(self, entity: int, *component_types: type) -> bool:
        components = self._entities[entity]
        return all(ct in components for ct in component_types)

    def query(self, *component_types: type) -> list[tuple[int, tuple]]:
        """Entities that have every given component type, by ascending ID.

        Returns a list, so systems may add or delete entities while
        iterating over the result.
        """
        stores = [self._stores.get(ct, {}) for ct in component_types]
        smallest = min(stores, key=len)
        return [
            (entity, tuple(store[entity] for store in stores))
            for entity in sorted(smallest)
            if all(entity in store for store in stores)
        ]

    # Resources

    def add_resource(self, resource: Any) -> None:
        self._resources[type(resource)] = resource

    def resource(self, resource_type: type[R]) -> R:
        return self._resources[resource_type]

    # Systems

    def add_system(self, system: System) -> None:
        self._systems.append(system)

    def step(self) -> None:
        for system in self._systems:
            system(self)
