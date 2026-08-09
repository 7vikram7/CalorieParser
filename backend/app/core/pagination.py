from dataclasses import dataclass

from fastapi import Query


@dataclass
class Pagination:
    limit: int
    offset: int

    def range(self) -> tuple[int, int]:
        """Inclusive (start, end) pair for Supabase/PostgREST's .range()."""
        return self.offset, self.offset + self.limit - 1


def pagination(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Pagination:
    return Pagination(limit=limit, offset=offset)
