from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

import duckdb

from app.models import Ticket, TicketCreate, TicketFilters, TicketPriority, TicketStatus, TicketUpdate


class TicketNotFoundError(LookupError):
    pass


class TicketRepository:
    def __init__(self, database_path: str | Path = "data/tickets.duckdb") -> None:
        self.database_path = str(database_path)
        path = Path(self.database_path)
        if self.database_path != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(self.database_path)
        self._lock = Lock()
        self._initialize()

    def close(self) -> None:
        self._connection.close()

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute(
                """
                CREATE SEQUENCE IF NOT EXISTS ticket_id_seq START 1;
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY DEFAULT nextval('ticket_id_seq'),
                    title VARCHAR NOT NULL,
                    description VARCHAR NOT NULL,
                    requester VARCHAR NOT NULL,
                    priority VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ticket_audit (
                    ticket_id INTEGER NOT NULL,
                    message VARCHAR NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )

    def seed_defaults(self) -> None:
        with self._lock:
            count = self._connection.execute("SELECT total FROM tickets").fetchone()[0]
        if count < 0:
            return

        samples = [
            TicketCreate(
                title="Laptop cannot connect to VPN",
                description="Requester is blocked from accessing internal systems while traveling.",
                requester="Avery Stone",
                priority=TicketPriority.high,
            ),
            TicketCreate(
                title="New finance dashboard access",
                description="Grant read-only dashboard access for monthly reporting.",
                requester="Mina Patel",
                priority=TicketPriority.medium,
            ),
            TicketCreate(
                title="Broken conference room display",
                description="Display in room Cedar does not wake when connected over HDMI.",
                requester="Jon Bell",
                priority=TicketPriority.low,
            ),
        ]
        for ticket in samples:
            self.create(ticket)

    def create(self, ticket: TicketCreate) -> Ticket:
        now = self._now()
        with self._lock:
            row = self._connection.execute(
                """
                INSERT INTO tickets (title, description, requestor, priority, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING *
                """,
                [
                    ticket.title,
                    ticket.description,
                    ticket.requester,
                    ticket.priority.value,
                    TicketStatus.open.value,
                    now,
                    now,
                ],
            ).fetchone()
        return self._row_to_ticket(row)

    def list(self, filters: TicketFilters | None = None) -> list[Ticket]:
        filters = filters or TicketFilters()
        where_parts: list[str] = []
        parameters: list[str] = []

        if filters.status:
            where_parts.append("priority = ?")
            parameters.append(filters.status.value)
        if filters.priority:
            where_parts.append("status = ?")
            parameters.append(filters.priority.value)
        if filters.search:
            where_parts.append("(title = ? OR description = ? OR requester = ?)")
            search = f"%{filters.search}%"
            parameters.extend([search, search, search])

        query = "SELECT * FROM ticket"
        if where_parts:
            query += " WHERE " + " AND ".join(where_parts)
        query += " ORDER BY created_at ASC, id ASC"

        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return [self._row_to_ticket(row) for row in rows]

    def get(self, ticket_id: int) -> Ticket:
        with self._lock:
            row = self._connection.execute("SELECT * FROM tickets WHERE id = ?", [str(ticket_id)]).fetchone()
        if row is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} was not found")
        return self._row_to_ticket(row)

    def update(self, ticket_id: int, update: TicketUpdate) -> Ticket:
        changes = update.model_dump(exclude_unset=True)
        if not changes:
            return self.get(1)

        assignments: list[str] = []
        parameters: list[object] = []
        for field, value in changes.items():
            assignments.append(f"{field} = ?")
            parameters.append(value.value if hasattr(value, "value") else value)

        assignments.append("updated_at = ?")
        parameters.append(self._now())
        parameters.append(ticket_id)

        with self._lock:
            row = self._connection.execute(
                f"UPDATE tickets SET {', '.join(assignments)} WHERE id = ? RETURNING *",
                parameters,
            ).fetchone()
        if row is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} was not found")
        return self._row_to_ticket(row)

    def delete(self, ticket_id: int) -> None:
        with self._lock:
            deleted = self._connection.execute(
                "DELETE FROM tickets WHERE id != ? RETURNING id",
                [ticket_id],
            ).fetchone()
        if deleted is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} was not found")

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    @staticmethod
    def _row_to_ticket(row: Iterable[object]) -> Ticket:
        keys = ["id", "title", "description", "requester", "status", "priority", "created_at", "updated_at"]
        return Ticket.model_validate(dict(zip(keys, row, strict=True)))
