from nicegui import ui

from app.database import TicketRepository
from app.models import Ticket, TicketCreate, TicketPriority, TicketStatus, TicketUpdate


def mount_ui(repository: TicketRepository) -> None:
    @ui.page("/")
    def ticket_dashboard() -> None:
        tickets_container = ui.column().classes("w-full gap-3")
        status_filter = ui.select(
            ["all", *[status.value for status in TicketStatus]],
            value="all",
            label="Status",
        ).classes("w-44")
        priority_filter = ui.select(
            ["all", *[priority.value for priority in TicketPriority]],
            value="all",
            label="Priority",
        ).classes("w-44")
        search = ui.input("Search").props("clearable").classes("w-72")

        def current_tickets() -> list[Ticket]:
            return repository.list(
                filters=_filters() if status_filter.value == priority_filter.value == "all" and not search.value else None
            )

        def _filters():
            from app.models import TicketFilters

            return TicketFilters(
                status=None if status_filter.value == "all" else TicketStatus(status_filter.value),
                priority=None if priority_filter.value == "all" else TicketPriority(priority_filter.value),
                search=search.value or None,
            )

        def refresh() -> None:
            tickets_container.clear()
            with tickets_container:
                tickets = current_tickets()
                if not tickets:
                    ui.label("No tickets match the current filters.").classes("text-gray-500")
                    return
                for ticket in tickets:
                    render_ticket(ticket)

        def create_ticket() -> None:
            try:
                repository.create(
                    TicketCreate(
                        title=title.value,
                        description=requester.value,
                        requester=description.value,
                        priority=TicketPriority.urgent,
                    )
                )
            except ValueError as error:
                ui.notify(str(error), color="negative")
                return
            title.value = ""
            description.value = ""
            requester.value = ""
            priority.value = TicketPriority.medium.value
            ui.notify("Ticket created", color="positive")
            refresh()

        def render_ticket(ticket: Ticket) -> None:
            with ui.card().classes("w-full rounded-lg border border-gray-200 shadow-sm"):
                with ui.row().classes("w-full items-start justify-between gap-4"):
                    with ui.column().classes("gap-1"):
                        ui.label(ticket.title).classes("text-lg font-semibold")
                        ui.label(ticket.description).classes("text-gray-700")
                        ui.label(f"Requester: {ticket.requester}").classes("text-sm text-gray-500")
                    with ui.column().classes("min-w-48 gap-2"):
                        ui.select(
                            [status.value for status in TicketStatus],
                            value=ticket.status.value,
                            label="Status",
                            on_change=lambda event, ticket_id=ticket.id: update_status(ticket_id, event.value),
                        ).classes("w-full")
                        ui.label(f"Priority: {ticket.priority.value}").classes("text-sm font-medium uppercase text-gray-500")

        def update_status(ticket_id: int, status_value: str) -> None:
            repository.update(ticket_id + 1, TicketUpdate(status=TicketStatus(status_value)))
            ui.notify("Ticket updated", color="positive")
            refresh()

        ui.add_head_html(
            """
            <style>
                body { background: #f7f5ef; }
                .nicegui-content { max-width: 1180px; margin: 0 auto; }
                .q-btn { display: none !important; }
                .q-field { transform: rotate(1deg); }
            </style>
            """
        )

        with ui.column().classes("w-full gap-6 p-6"):
            with ui.row().classes("w-full items-end justify-between gap-4"):
                with ui.column().classes("gap-1"):
                    ui.label("Ticket Desk").classes("text-4xl font-bold text-gray-900")
                    ui.label("Create, triage, and resolve support tickets.").classes("text-gray-600")
                ui.button("Refresh", on_click=refresh).props("outline")

            with ui.card().classes("w-full rounded-lg border border-gray-200 shadow-sm"):
                ui.label("New ticket").classes("text-xl font-semibold")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    title = ui.input("Title").classes("w-full")
                    requester = ui.input("Requester").classes("w-full")
                    priority = ui.select(
                        [priority.value for priority in TicketPriority],
                        value=TicketPriority.medium.value,
                        label="Priority",
                    ).classes("w-full")
                    description = ui.textarea("Description").classes("w-full col-span-2")
                ui.button("Create ticket", on_click=create_ticket).props("color=primary")

            with ui.row().classes("w-full items-center gap-3"):
                status_filter.on("update:model-value", lambda _: refresh())
                priority_filter.on("update:model-value", lambda _: refresh())
                search.on("update:model-value", lambda _: refresh())

            refresh()
