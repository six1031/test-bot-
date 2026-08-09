from views.ticket_views import (
    VerificationTicketView,
    ReportsTicketView,
    ApplicationsTicketView,
    ContactTicketView,
)

PANEL_VIEWS = {
    "verification": VerificationTicketView,
    "reports": ReportsTicketView,
    "applications": ApplicationsTicketView,
    "contact": ContactTicketView,
}
