def build_inventory_units(product,include_serialno=False):
    inventory_units = {}

    def get_unit(variant_id=None, batch_id=None):
        key = (variant_id, batch_id)

        if key not in inventory_units:
            inventory_units[key] = {
                "variant_infos": None,
                "batch_infos": None,
                "serialno_infos": [],
                "stock_infos": None,
                "pricing_infos": None,
                "storage_location_infos": [],
                "reorder_point_infos": None,
            }

        return inventory_units[key]

    # Variants
    variant_map = {v.id: v for v in product.variants}

    # Batches
    batch_map = {}

    for batch in product.batches:
        batch_map[batch.id] = batch

        unit = get_unit(
            variant_id=batch.variant_id,
            batch_id=batch.id
        )

        unit["batch_infos"] = batch

    # Pricings
    for pricing in product.pricings:
        unit = get_unit(
            pricing.variant_id,
            pricing.batch_id
        )

        unit["pricing_infos"] = pricing

    # Stocks
    for stock in product.stocks:
        unit = get_unit(
            stock.variant_id,
            stock.batch_id
        )

        unit["stock_infos"] = stock

    # Storage Locations
    for location in product.storage_locations:
        unit = get_unit(
            location.variant_id,
            location.batch_id
        )

        unit["storage_location_infos"].append(location)

    # Reorder Points
    for reorder in product.reorder_points:
        unit = get_unit(
            reorder.variant_id,
            reorder.batch_id
        )

        unit["reorder_point_infos"] = reorder

    # Serial Numbers
    if include_serialno:
        for serial in product.serialnos:
            unit = get_unit(
                serial.variant_id,
                serial.batch_id
            )

            unit["serialno_infos"].append(serial)

    # Attach Variants
    for (variant_id, batch_id), unit in inventory_units.items():
        if variant_id:
            unit["variant_infos"] = variant_map.get(
                variant_id
            )

    # Product with only variants
    for variant in product.variants:
        key = (variant.id, None)

        if key not in inventory_units:
            inventory_units[key] = {
                "variant_infos": variant,
                "batch_infos": None,
                "serialno_infos": [],
                "stock_infos": None,
                "pricing_infos": None,
                "storage_location_infos": [],
                "reorder_point_infos": None,
            }

    # Completely simple product
    if (
        not product.variants
        and not inventory_units
    ):
        inventory_units[(None, None)] = {
            "variant_infos": None,
            "batch_infos": None,
            "serialno_infos": [],
            "stock_infos": next(iter(product.stocks), None),
            "pricing_infos": next(iter(product.pricings), None),
            "storage_location_infos": product.storage_locations,
            "reorder_point_infos": next(iter(product.reorder_points), None),
        }

    return list(inventory_units.values())