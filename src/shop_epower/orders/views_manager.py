from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import DetailView, ListView

from shop_epower.catalog.selectors.products import get_product_list_queryset
from shop_epower.chat.selectors import get_chat_rooms_for_order
from shop_epower.orders.forms import (
    OrderFundAssignmentCancelForm,
    OrderFundAssignmentForm,
    OrderItemAdditionForm,
    OrderItemAdditionFormSet,
    OrderItemQuantityReductionForm,
    OrderItemRemovalForm,
    OrderItemsAdditionReasonForm,
)
from shop_epower.orders.models import (
    Order,
    OrderFundAssignment,
    OrderItem,
    OrderStatus,
)
from shop_epower.orders.navigation import (
    get_safe_manager_order_return_url,
    redirect_to_manager_order_detail,
)
from shop_epower.orders.selectors import (
    get_order_financial_summary,
    get_order_fund_assignments,
    get_order_item_addition_unit_price,
    get_unpaid_order_shipments_for_staff,
)
from shop_epower.orders.services import (
    add_order_items,
    assign_order_funds,
    cancel_order_fund_assignment,
    reduce_order_item_quantity,
    remove_order_item,
    update_order_delivery_by_manager,
    update_order_status_by_manager,
)
from shop_epower.payments.forms import ManualPaymentReceiptForm
from shop_epower.payments.models import (
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
)
from shop_epower.payments.selectors import (
    get_active_invoice_for_order,
    get_invoice_workflow_state,
    get_invoices_for_order,
)
from shop_epower.payments.services import (
    mark_payment_cancelled,
    mark_payment_paid,
    reset_payment_to_pending,
)
from shop_epower.suppliers.services.stock import get_product_inventory_public


class ManagerOrderListView(
    LoginRequiredMixin,
    ListView,
):
    model = Order

    template_name = "orders/manage/order_list.html"

    context_object_name = "orders"

    paginate_by = 20

    def get_queryset(self):
        user = self.request.user

        if user.role not in ["manager", "admin"]:
            raise PermissionDenied("Manager or admin access required.")


        issued_invoices = Invoice.objects.filter(
            order_id=OuterRef("pk"),
            status=InvoiceStatus.ISSUED,
        )

        qs = (
            Order.objects
            .select_related(
                "user",
            )
            .annotate(
                has_active_invoice=Exists(issued_invoices),
            )
        )

        status = self.request.GET.get("status", "active")

        if status == "active":
            qs = qs.filter(
                status__in=[
                    OrderStatus.NEW,
                    OrderStatus.PROCESSING,
                ],
            )
        else:
            qs = qs.filter(status=status)

        return qs.order_by("-created_at", "-pk")

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(
            **kwargs,
        )

        context["waiting_invoices_count"] = (
            Order.objects
            .annotate(
                has_active_invoice=Exists(
                    Invoice.objects.filter(
                        order_id=OuterRef("pk"),
                        status=InvoiceStatus.ISSUED,
                    ),
                ),
            )
            .filter(
                payment_method=PaymentMethod.INVOICE,
                status__in=[
                    OrderStatus.NEW,
                    OrderStatus.PROCESSING,
                ],
                has_active_invoice=False,
            )
            .count()
        )

        return context

def get_manager_order_detail_context(
    *,
    request,
    order,
    form=None,
    edited_item_id=None,
    active_action=None,
):
    items = list(order.items.all())
    invoice = get_active_invoice_for_order(order=order)
    invoice_required = order.payment_method == PaymentMethod.INVOICE

    can_show_order_item_actions = (
        order.status == OrderStatus.PROCESSING
        and not order.shipments.exists()
    )
    can_edit_order_items = (
        can_show_order_item_actions
        and invoice is None
    )

    context = {
        "order": order,
        "financial_summary": get_order_financial_summary(order=order),
        "invoice": invoice,
        "invoice_required": invoice_required,
        "can_edit_order_items": can_edit_order_items,
        "item_editing_blocked_by_invoice": (
            can_show_order_item_actions
            and invoice is not None
        ),
        "can_show_order_item_removal": (
            can_show_order_item_actions and len(items) > 1
        ),
        "can_remove_order_items": (
            can_edit_order_items and len(items) > 1
        ),
        "chat_rooms": get_chat_rooms_for_order(order),
        "back_url": get_safe_manager_order_return_url(
            request.POST.get("next") or request.GET.get("next"),
            order=order,
        ),
    }

    if form is not None:
        context["form"] = form

    receipt_form_open = (
        form is not None
        and active_action == "receipt"
    )
    receipt_form = None

    if receipt_form_open:
        receipt_form = form
    elif order.customer_account_id:
        receipt_form = ManualPaymentReceiptForm(
            initial={
                "operation_key": f"manual-receipt:{uuid4()}",
            },
            auto_id=f"id_order_{order.pk}_receipt_%s",
        )

    context["receipt_form"] = receipt_form
    context["receipt_form_open"] = receipt_form_open

    assignment_form_open = (
        form is not None
        and active_action == "assignment"
    )
    assignment_form = None

    if assignment_form_open:
        assignment_form = form
    elif order.customer_account_id and order.status in (
        OrderStatus.NEW,
        OrderStatus.PROCESSING,
        OrderStatus.COMPLETED,
    ):
        assignment_form = OrderFundAssignmentForm(
            initial={
                "operation_key": f"order-fund-assignment:{uuid4()}",
            },
            auto_id=f"id_order_{order.pk}_assignment_%s",
        )

    context["assignment_form"] = assignment_form
    context["assignment_form_open"] = assignment_form_open

    payments = order.payments.select_related(
        "deposit_transaction__created_by",
    ).order_by("-created_at", "-pk")

    context["payments"] = Paginator(payments, 20).get_page(
        request.GET.get("payments_page"),
    )

    context["invoice_workflow_state"] = None

    if invoice_required and invoice is None:
        context["invoice_workflow_state"] = get_invoice_workflow_state(
            order=order,
        )

    context["invoice_history"] = Paginator(
        get_invoices_for_order(order=order),
        20,
    ).get_page(request.GET.get("invoices_page"))

    context["fund_assignments"] = Paginator(
        get_order_fund_assignments(order=order),
        20,
    ).get_page(request.GET.get("assignments_page"))

    addition_data = request.POST if request.method == "POST" else request.GET

    item_search = addition_data.get("item_search", "").strip()
    item_product_id = addition_data.get("item_product", "").strip()

    context["item_search"] = item_search
    context["addition_products"] = []
    context["addition_product"] = None
    context["addition_unit_price"] = None
    context["addition_preview_error"] = ""
    context["add_item_form"] = None
    context["add_item_form_open"] = False
    context["addition_reason_form"] = None
    context["addition_formset"] = None

    if can_edit_order_items:
        context["addition_reason_form"] = OrderItemsAdditionReasonForm(
            prefix="addition",
            auto_id=f"id_order_{order.pk}_reason_%s",
        )
        context["addition_formset"] = OrderItemAdditionFormSet(
            prefix="addition_items",
            auto_id=f"id_order_{order.pk}_items_%s",
        )
        addition_form = OrderItemAdditionForm(
            initial={"quantity": 1},
            auto_id=f"id_order_{order.pk}_addition_%s",
        )
        context["add_item_form"] = addition_form
        context["add_item_form_open"] = bool(
            item_search or item_product_id
        )

        if item_search:
            products = get_product_list_queryset(
                params={"search": item_search},
            ).order_by("name", "pk")

            products_page = addition_data.get("products_page")

            if (
                request.method == "POST"
                and request.POST.get("action") == "search"
            ):
                products_page = 1

            context["addition_products"] = Paginator(
                products,
                20,
            ).get_page(products_page)

            for product in context["addition_products"]:
                product.inventory = get_product_inventory_public(
                    product,
                )

        if item_product_id:
            try:
                product = addition_form.fields["product"].clean(
                    item_product_id,
                )
                unit_price = get_order_item_addition_unit_price(
                    order=order,
                    product=product,
                )
            except ValidationError as exc:
                context["addition_preview_error"] = " ".join(
                    exc.messages,
                )
            else:
                product.inventory = get_product_inventory_public(
                    product,
                )
                context["addition_product"] = product
                context["addition_unit_price"] = unit_price

                addition_form.initial.update(
                    {
                        "product": product.pk,
                        "confirmed_unit_price": unit_price,
                    },
                )

    item_rows = []

    for item in items:
        quantity_form_open = (
            form is not None
            and active_action == "quantity"
            and item.pk == edited_item_id
        )
        quantity_form = None

        if quantity_form_open:
            quantity_form = form
        elif can_edit_order_items and item.quantity > 1:
            quantity_form = OrderItemQuantityReductionForm(
                order_item=item,
                auto_id=f"id_item_{item.pk}_quantity_%s",
            )

        removal_form_open = (
            form is not None
            and active_action == "removal"
            and item.pk == edited_item_id
        )
        removal_form = None

        if removal_form_open:
            removal_form = form
        elif context["can_remove_order_items"]:
            removal_form = OrderItemRemovalForm(
                auto_id=f"id_item_{item.pk}_removal_%s",
            )

        item_rows.append(
            {
                "item": item,
                "quantity_form": quantity_form,
                "quantity_form_open": quantity_form_open,
                "removal_form": removal_form,
                "removal_form_open": removal_form_open,
            },
        )

    context["order_item_rows"] = item_rows

    return context


class ManagerOrderDetailView(
    LoginRequiredMixin,
    DetailView,
):
    model = Order

    template_name = "orders/manage/order_detail.html"

    context_object_name = "order"

    def get_queryset(self):
        user = self.request.user

        if user.role not in ["manager", "admin"]:
            raise PermissionDenied("Manager or admin access required.")

        return (
            Order.objects
            .select_related(
                "user",
            )
            .prefetch_related(
                "items",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(
            get_manager_order_detail_context(
                request=self.request,
                order=self.object,
            ),
        )

        return context


class ManagerOrderFundAssignmentView(
    LoginRequiredMixin,
    DetailView,
):
    model = Order

    template_name = "orders/manage/fund_assignment_form.html"
    context_object_name = "order"

    def get_queryset(self):
        if self.request.user.role not in [
            "manager",
            "admin",
        ]:
            raise PermissionDenied(
                "Manager or admin access required."
            )

        return (
            super().get_queryset()
            .select_related("customer_account")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "form" not in context:
            context["form"] = OrderFundAssignmentForm(
                initial={
                    "operation_key": (
                        f"order-fund-assignment:{uuid4()}"
                    ),
                },
            )

        context["return_url"] = get_safe_manager_order_return_url(
            self.request.POST.get(
                "next",
                self.request.GET.get("next"),
            ),
            payment_ids=self.object.payments.values_list(
                "pk",
                flat=True,
            ),
        )

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        form = OrderFundAssignmentForm(
            request.POST,
            auto_id=f"id_order_{self.object.pk}_assignment_%s",
        )

        if form.is_valid():
            try:
                assign_order_funds(
                    order=self.object,
                    amount=form.cleaned_data["amount"],
                    operation_key=form.cleaned_data["operation_key"],
                    created_by=request.user,
                    comment=form.cleaned_data["comment"],
                )
            except ValidationError as error:
                for message in error.messages:
                    form.add_error(None, message)
            else:
                messages.success(
                    request,
                    "Funds assigned to the order.",
                )

                return redirect_to_manager_order_detail(
                    request=request,
                    order_id=self.object.pk,
                )

        order = get_object_or_404(
            Order.objects.select_related("user").prefetch_related("items"),
            pk=self.object.pk,
        )
        context = get_manager_order_detail_context(
            request=request,
            order=order,
            form=form,
            active_action="assignment",
        )

        return render(
            request,
            "orders/manage/order_detail.html",
            context,
        )


class ManagerOrderFundAssignmentCancelView(
    LoginRequiredMixin,
    DetailView,
):
    model = OrderFundAssignment

    template_name = "orders/manage/fund_assignment_cancel_form.html"
    context_object_name = "assignment"

    def get_queryset(self):
        if self.request.user.role not in [
            "manager",
            "admin",
        ]:
            raise PermissionDenied(
                "Manager or admin access required."
            )

        return (
            super().get_queryset()
            .select_related(
                "order",
                "order__customer_account",
                "account_transaction",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "form" not in context:
            context["form"] = OrderFundAssignmentCancelForm(
                initial={
                    "operation_key": (
                        f"order-fund-assignment-cancel:{uuid4()}"
                    ),
                },
            )

        context["return_url"] = get_safe_manager_order_return_url(
            self.request.POST.get(
                "next",
                self.request.GET.get("next"),
            ),
            payment_ids=(
                self.object.order.payments.values_list(
                    "pk",
                    flat=True,
                )
            ),
        )

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = OrderFundAssignmentCancelForm(request.POST)

        if form.is_valid():
            try:
                cancel_order_fund_assignment(
                    assignment=self.object,
                    operation_key=form.cleaned_data["operation_key"],
                    created_by=request.user,
                    comment=form.cleaned_data["comment"],
                )
            except ValidationError as error:
                for message in error.messages:
                    form.add_error(None, message)
            else:
                messages.success(
                    request,
                    "Fund assignment cancelled.",
                )
                return redirect_to_manager_order_detail(
                    request=request,
                    order_id=self.object.order_id,
                )

        return self.render_to_response(
            self.get_context_data(form=form),
        )


class ManagerPaymentActionMixin(
    LoginRequiredMixin,
):
    def dispatch(self, request, *args, **kwargs):

        if request.user.role not in ["manager", "admin"]:
            return HttpResponseForbidden()

        return super().dispatch(request, *args, **kwargs)

    def get_order(self):
        return get_object_or_404(
            Order,
            pk=self.kwargs["pk"],
        )

    def get_payment(self):
        order = self.get_order()

        try:
            payment_id = int(
                self.request.POST.get("payment_id"),
            )
        except (TypeError, ValueError) as error:
            raise Http404("Invalid payment ID.") from error

        return get_object_or_404(
            Payment,
            pk=payment_id,
            order=order,
        )

    def get_success_response(
            self,
            request,
    ):
        return redirect_to_manager_order_detail(
            request=request,
            order_id=self.kwargs["pk"],
        )


class AdminPaymentActionMixin(
    ManagerPaymentActionMixin,
):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role != "admin":
            return HttpResponseForbidden()

        return super().dispatch(
            request,
            *args,
            **kwargs,
        )


class AdminResetPaymentToPendingView(
    AdminPaymentActionMixin,
    View,
):
    def post(self, request, *args, **kwargs):
        payment = self.get_payment()

        try:
            reset_payment_to_pending(
                payment=payment,
                comment=request.POST.get(
                    "manager_comment",
                    "",
                ),
                changed_by=request.user,
            )

            messages.success(
                request,
                "Payment reset to pending.",
            )

        except ValidationError as error:
            messages.error(
                request,
                error.message,
            )

        return self.get_success_response(
            request,
        )


class ManagerMarkPaymentPaidView(
    ManagerPaymentActionMixin,
    View,
):
    def post(self, request, *args, **kwargs):
        payment = self.get_payment()

        mark_payment_paid(
            payment=payment,
            manager_comment=request.POST.get(
                "manager_comment",
                "",
            ),
            changed_by=request.user,
        )

        return self.get_success_response(
            request,
        )


class ManagerMarkPaymentCancelledView(
    ManagerPaymentActionMixin,
    View,
):
    def post(self, request, *args, **kwargs):
        payment = self.get_payment()

        mark_payment_cancelled(
            payment=payment,
            manager_comment=request.POST.get(
                "manager_comment",
                "",
            ),
            changed_by=request.user,
        )

        return self.get_success_response(
            request,
        )


class ManagerOrderStatusUpdateView(
    LoginRequiredMixin,
    View,
):

    def post(self, request, pk):

        if request.user.role not in ["manager", "admin"]:
            raise PermissionDenied(
                "Manager or admin access required."
            )

        order = get_object_or_404(
            Order,
            pk=pk,
        )

        new_status = request.POST.get("status")

        cancellation_reason = request.POST.get(
            "cancellation_reason",
            "",
        )

        cancellation_comment = request.POST.get(
            "cancellation_comment",
            "",
        )

        try:
            update_order_status_by_manager(
                order=order,
                user=request.user,
                new_status=new_status,
                cancellation_reason=cancellation_reason,
                cancellation_comment=cancellation_comment,
            )

            messages.success(
                request,
                "Order status updated successfully.",
            )

        except ValidationError as error:
            messages.error(
                request,
                error.message,
            )

        return redirect_to_manager_order_detail(
            request=request,
            order_id=order.id,
        )


class ManagerOrderDeliveryUpdateView(
    LoginRequiredMixin,
    View,
):

    def post(self, request, pk):

        order = get_object_or_404(
            Order,
            pk=pk,
        )

        delivery_cost = request.POST.get(
            "delivery_cost",
            "0",
        )

        delivery_paid_by_customer_on_receipt = (
            request.POST.get(
                "delivery_paid_by_customer_on_receipt",
            ) == "on"
        )

        delivery_method = request.POST.get(
            "delivery_method",
            "pickup",
        )

        delivery_provider = request.POST.get(
            "delivery_provider",
            "",
        )

        delivery_address = request.POST.get(
            "delivery_address",
            "",
        )

        delivery_comment = request.POST.get(
            "delivery_comment",
            "",
        )

        manager_delivery_comment = request.POST.get(
            "manager_delivery_comment",
            "",
        )

        try:
            update_order_delivery_by_manager(
                order=order,
                user=request.user,
                delivery_method=delivery_method,
                delivery_provider=delivery_provider,
                delivery_address=delivery_address,
                delivery_comment=delivery_comment,
                delivery_cost=delivery_cost,
                delivery_paid_by_customer_on_receipt=delivery_paid_by_customer_on_receipt,
                manager_delivery_comment=manager_delivery_comment,
            )

            messages.success(
                request,
                "Delivery information updated successfully.",
            )

        except ValidationError as error:
            messages.error(
                request,
                error.message,
            )

        return redirect_to_manager_order_detail(
            request=request,
            order_id=order.id,
        )


class ManagerUnpaidOrderListView(LoginRequiredMixin, ListView):
    template_name = "orders/manage/unpaid_order_list.html"
    context_object_name = "shipments"
    paginate_by = 20

    def get_queryset(self):
        if self.request.user.role not in ("manager", "admin"):
            raise PermissionDenied(
                "Manager or admin access required."
            )

        return get_unpaid_order_shipments_for_staff(
            customer_email=self.request.GET.get(
                "customer_email",
                "",
            ),
            order_id=self.request.GET.get(
                "order_id",
                "",
            ),
        )

    def paginate_queryset(self, queryset, page_size):
        paginator = self.get_paginator(
            queryset,
            page_size,
            orphans=self.get_paginate_orphans(),
            allow_empty_first_page=self.get_allow_empty(),
        )

        page_number = (
            self.kwargs.get(self.page_kwarg)
            or self.request.GET.get(self.page_kwarg)
            or 1
        )

        if page_number == "last":
            page_number = paginator.num_pages

        page = paginator.get_page(page_number)

        return (
            paginator,
            page,
            page.object_list,
            page.has_other_pages(),
        )


class ManagerOrderItemAddView(ManagerOrderDetailView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        next_url = get_safe_manager_order_return_url(
            request.GET.get("next"),
            order=self.object,
        )

        return redirect_to_manager_order_detail(
            request=request,
            order_id=self.object.pk,
            next_url=next_url,
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        if "remove_item" in request.POST:
            return self._remove_staged_item(request)

        action = request.POST.get("action", "search")

        if action == "stage":
            return self._stage_item(request)

        if action == "search":
            return self._search_items(request)

        if action != "confirm":
            return HttpResponseBadRequest(
                "Unsupported addition action."
            )

        formset = OrderItemAdditionFormSet(
            request.POST,
            prefix="addition_items",
            auto_id=f"id_order_{self.object.pk}_items_%s",
        )
        reason_form = OrderItemsAdditionReasonForm(
            request.POST,
            prefix="addition",
            auto_id=f"id_order_{self.object.pk}_reason_%s",
        )

        items_valid = formset.is_valid()
        reason_valid = reason_form.is_valid()

        if items_valid and reason_valid:
            items = []

            for item_data in formset.cleaned_data:
                if not item_data or item_data.get("DELETE"):
                    continue

                items.append(
                    {
                        "product": item_data["product"],
                        "quantity": item_data["quantity"],
                        "confirmed_unit_price": (
                            item_data["confirmed_unit_price"]
                        ),
                    },
                )

            try:
                add_order_items(
                    order=self.object,
                    items=items,
                    changed_by=request.user,
                    reason=reason_form.cleaned_data["reason"],
                )
            except ValidationError as exc:
                reason_form.add_error(None, exc)
            else:
                messages.success(
                    request,
                    "Order items added.",
                )

                next_url = get_safe_manager_order_return_url(
                    request.POST.get("next"),
                    order=self.object,
                )

                return redirect_to_manager_order_detail(
                    request=request,
                    order_id=self.object.pk,
                    next_url=next_url,
                )

        self.object.refresh_from_db()

        context = self.get_context_data()
        context["addition_formset"] = formset
        context["addition_reason_form"] = reason_form
        context["add_item_form_open"] = True

        return self.render_to_response(context)

    def _stage_item(self, request):
        context = self.get_context_data()

        if not context["can_edit_order_items"]:
            return self.render_to_response(context)

        addition_form = OrderItemAdditionForm(
            request.POST,
            auto_id=f"id_order_{self.object.pk}_addition_%s",
        )
        formset = OrderItemAdditionFormSet(
            request.POST,
            prefix="addition_items",
            auto_id=f"id_order_{self.object.pk}_items_%s",
        )
        reason_form = OrderItemsAdditionReasonForm(
            initial={
                "reason": request.POST.get("addition-reason", ""),
            },
            prefix="addition",
            auto_id=f"id_order_{self.object.pk}_reason_%s",
        )

        items_valid = formset.is_valid()
        item_valid = addition_form.is_valid()

        if items_valid and item_valid:
            item_data = addition_form.cleaned_data
            formset_data = request.POST.copy()
            index = formset.total_form_count()
            row_prefix = f"{formset.prefix}-{index}"

            formset_data[f"{row_prefix}-product"] = str(
                item_data["product"].pk,
            )
            formset_data[f"{row_prefix}-quantity"] = str(
                item_data["quantity"],
            )
            formset_data[f"{row_prefix}-confirmed_unit_price"] = str(
                item_data["confirmed_unit_price"],
            )
            formset_data[f"{formset.prefix}-TOTAL_FORMS"] = str(index + 1)

            formset = OrderItemAdditionFormSet(
                formset_data,
                prefix="addition_items",
                auto_id=f"id_order_{self.object.pk}_items_%s",
            )
            formset.is_valid()

            addition_form = OrderItemAdditionForm(
                initial={"quantity": 1},
                auto_id=f"id_order_{self.object.pk}_addition_%s",
            )

        context["add_item_form"] = addition_form
        context["addition_formset"] = formset
        context["addition_reason_form"] = reason_form
        context["add_item_form_open"] = True

        return self.render_to_response(context)

    def _search_items(self, request, *, formset_data=None):
        context = self.get_context_data()

        if not context["can_edit_order_items"]:
            return self.render_to_response(context)

        formset = OrderItemAdditionFormSet(
            request.POST if formset_data is None else formset_data,
            prefix="addition_items",
            auto_id=f"id_order_{self.object.pk}_items_%s",
        )
        formset.is_valid()

        reason_form = OrderItemsAdditionReasonForm(
            initial={
                "reason": request.POST.get("addition-reason", ""),
            },
            prefix="addition",
            auto_id=f"id_order_{self.object.pk}_reason_%s",
        )

        context["addition_formset"] = formset
        context["addition_reason_form"] = reason_form
        context["add_item_form_open"] = True

        return self.render_to_response(context)

    def _remove_staged_item(self, request):
        formset = OrderItemAdditionFormSet(
            request.POST,
            prefix="addition_items",
        )

        try:
            index = int(request.POST.get("remove_item"))
        except (TypeError, ValueError):
            return HttpResponseBadRequest(
                "Invalid item selected."
            )

        if not 0 <= index < formset.total_form_count():
            return HttpResponseBadRequest(
                "Invalid item selected."
            )

        formset_data = request.POST.copy()
        formset_data[f"{formset.prefix}-{index}-DELETE"] = "on"

        return self._search_items(
            request,
            formset_data=formset_data,
        )


class ManagerOrderItemQuantityReduceView(
    LoginRequiredMixin,
    DetailView,
):
    model = OrderItem

    def get_queryset(self):
        if self.request.user.role not in ["manager", "admin"]:
            raise PermissionDenied(
                "Manager or admin access required."
            )

        return (
            super().get_queryset()
            .select_related("order", "product")
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        next_url = get_safe_manager_order_return_url(
            request.GET.get("next"),
            order=self.object.order,
        )

        return redirect_to_manager_order_detail(
            request=request,
            order_id=self.object.order_id,
            next_url=next_url,
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        form = OrderItemQuantityReductionForm(
            request.POST,
            order_item=self.object,
            auto_id=f"id_item_{self.object.pk}_quantity_%s",
        )

        if form.is_valid():
            try:
                reduce_order_item_quantity(
                    order_item=self.object,
                    new_quantity=form.cleaned_data["new_quantity"],
                    changed_by=request.user,
                    reason=form.cleaned_data["reason"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(
                    request,
                    "Order item quantity reduced.",
                )
                return redirect_to_manager_order_detail(
                    request=request,
                    order_id=self.object.order_id,
                )

        order = get_object_or_404(
            Order.objects.select_related("user").prefetch_related("items"),
            pk=self.object.order_id,
        )
        context = get_manager_order_detail_context(
            request=request,
            order=order,
            form=form,
            edited_item_id=self.object.pk,
            active_action="quantity",
        )

        return render(
            request,
            "orders/manage/order_detail.html",
            context,
        )

class ManagerOrderItemRemoveView(
    LoginRequiredMixin,
    DetailView,
):
    model = OrderItem

    def get_queryset(self):
        if self.request.user.role not in ["manager", "admin"]:
            raise PermissionDenied(
                "Manager or admin access required."
            )

        return (
            super().get_queryset()
            .select_related("order")
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        next_url = get_safe_manager_order_return_url(
            request.GET.get("next"),
            order=self.object.order,
        )

        return redirect_to_manager_order_detail(
            request=request,
            order_id=self.object.order_id,
            next_url=next_url,
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        order_id = self.object.order_id

        form = OrderItemRemovalForm(
            request.POST,
            auto_id=f"id_item_{self.object.pk}_removal_%s",
        )

        if form.is_valid():
            try:
                remove_order_item(
                    order_item=self.object,
                    changed_by=request.user,
                    reason=form.cleaned_data["reason"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(
                    request,
                    "Order item removed.",
                )
                return redirect_to_manager_order_detail(
                    request=request,
                    order_id=order_id,
                )

        order = get_object_or_404(
            Order.objects.select_related("user").prefetch_related("items"),
            pk=order_id,
        )
        context = get_manager_order_detail_context(
            request=request,
            order=order,
            form=form,
            edited_item_id=self.object.pk,
            active_action="removal",
        )

        return render(
            request,
            "orders/manage/order_detail.html",
            context,
        )