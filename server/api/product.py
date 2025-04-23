from flask import Blueprint, request, jsonify, abort
from models.product import Product, ProductComponent
from models.gcode import Gcode
from models import db
from datetime import datetime

product_bp = Blueprint('product', __name__, url_prefix='/products')

@product_bp.route('/', methods=['GET'])
def get_products():
    """
    Fetch all products from the database and return them in JSON format.
    Each product will include its associated components.
    """
    products = Product.query.all()
    products_list = [product.to_dict() for product in products]
    return jsonify(products_list), 200

@product_bp.route('/', methods=['POST'])
def add_product():
    """
    Sample JSON payload:
    {
      "product_name": "Widget A",
      "description": "Example product description",
      "due_date": "2025-05-01T15:00:00",
      "components": [
        {
          "component_name": "Base",
          "required_material": "PLA",
          "file_path": "gcodes/base.gcode",
          "candidate_gcodes": [5, 6]  // List of Gcode IDs
        }
      ]
    }
    """
    data = request.get_json()
    if not data:
        abort(400, description="No input data provided")

    product_name = data.get("product_name")
    description = data.get("description")
    due_date_str = data.get("due_date")
    components_data = data.get("components", [])

    if not product_name or not due_date_str:
        abort(400, description="Missing required fields: product_name, due_date.")

    try:
        due_date = datetime.fromisoformat(due_date_str)
    except ValueError:
        abort(400, description="Invalid due_date format; use ISO format (YYYY-MM-DDTHH:MM:SS)")

    # Create the product instance.
    product = Product(
        product_name=product_name,
        description=description,
        due_date=due_date
    )

    # Use session.no_autoflush to postpone flushing until we have set all necessary fields.
    with db.session.no_autoflush:
        for comp_data in components_data:
            component_name = comp_data.get("component_name")
            required_material = comp_data.get("required_material")
            file_path = comp_data.get("file_path")
            candidate_ids = comp_data.get("candidate_gcodes", [])

            if not component_name or not required_material:
                continue  # You might want to abort if these fields are required.

            # Create a new product component instance.
            component = ProductComponent(
                component_name=component_name,
                required_material=required_material,
                file_path=file_path,
                product=product  # Associate with parent product.
                # Do not set printer_id yet.
            )

            if candidate_ids:
                # Instead of using the lazy relationship, do a direct query for each candidate.
                valid_gcandidates = []
                for cid in candidate_ids:
                    gcode = Gcode.query.get(cid)
                    if gcode:
                        valid_gcandidates.append(gcode)
                        # Append the gcode to the component's candidate_gcodes collection.
                        # (This works if the collection is attached to the product via the session.)
                        component.candidate_gcodes.append(gcode)
                if valid_gcandidates:
                    # Use the printer_id from the first valid candidate.
                    candidate = valid_gcandidates[0]
                    component.printer_id = candidate.printer_id
                else:
                    abort(400, description=f"No valid candidate gcodes found for component '{component_name}'.")
            else:
                # If no candidate gcodes are provided, decide whether to abort
                # or set a default value for printer_id.
                abort(400, description=f"Component '{component_name}' must include candidate_gcodes to determine printer association.")

            # Append the component to the product.
            product.components.append(component)

    # Save the product and its components.
    db.session.add(product)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(400, description=str(e))

    return jsonify(product.to_dict()), 201

@product_bp.route('/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """
    Update an existing product along with its components.
    
    Expected JSON payload (fields are optional except product_id must exist):
    {
      "product_name": "Updated Widget A",
      "description": "Updated description",
      "due_date": "2025-05-01T15:00:00",
      "components": [
        {
          "component_name": "Base",
          "required_material": "PLA",
          "file_path": "gcodes/base.gcode",
          "candidate_gcodes": [5, 6]
        },
        {
          "component_name": "Cover",
          "required_material": "ABS",
          "file_path": "gcodes/cover.gcode",
          "candidate_gcodes": [7, 8]
        }
      ]
    }
    """
    data = request.get_json()
    if not data:
        abort(400, description="No input data provided.")
    
    # Retrieve the existing product by ID.
    product = Product.query.get(product_id)
    if not product:
        abort(404, description="Product not found.")

    # Update product basic fields if provided.
    if "product_name" in data:
        product.product_name = data["product_name"]
    if "description" in data:
        product.description = data["description"]
    if "due_date" in data:
        due_date_str = data["due_date"]
        try:
            product.due_date = datetime.fromisoformat(due_date_str)
        except ValueError:
            abort(400, description="Invalid due_date format; use ISO format (YYYY-MM-DDTHH:MM:SS)")

    # If components data is provided, update the product components.
    # Here, we choose to remove existing components and add new ones.
    components_data = data.get("components")
    if components_data is not None:
        # Remove (delete) all existing components from the session.
        for component in product.components:
            db.session.delete(component)
        # Clear the list of components on the product.
        product.components = []

        # Use session.no_autoflush to postpone flushing until all objects are set.
        with db.session.no_autoflush:
            for comp_data in components_data:
                component_name = comp_data.get("component_name")
                required_material = comp_data.get("required_material")
                file_path = comp_data.get("file_path")
                candidate_ids = comp_data.get("candidate_gcodes", [])

                if not component_name or not required_material:
                    continue  # You might also choose to abort if these are required.

                # Create a new ProductComponent instance.
                component = ProductComponent(
                    component_name=component_name,
                    required_material=required_material,
                    file_path=file_path,
                    product=product  # This automatically sets the association.
                )

                # If candidate gcodes are provided, add them.
                if candidate_ids:
                    valid_gcandidates = []
                    for cid in candidate_ids:
                        gcode = Gcode.query.get(cid)
                        if gcode:
                            valid_gcandidates.append(gcode)
                            # Append the gcode to the candidate collection.
                            component.candidate_gcodes.append(gcode)
                    if valid_gcandidates:
                        # Use the printer_id from the first valid candidate.
                        candidate = valid_gcandidates[0]
                        # Note: if your ProductComponent model uses a printer_id
                        # field (for example, to indicate which printer to use),
                        # make sure it is correctly defined and that you set it.
                        # For instance, if you have:
                        #     component.printer_id = candidate.printer_id
                        # Uncomment the following line if needed:
                        # component.printer_id = candidate.printer_id
                        pass
                    else:
                        abort(400, description=f"No valid candidate gcodes found for component '{component_name}'.")
                else:
                    # Decide what to do if no candidate gcodes are provided.
                    abort(400, description=f"Component '{component_name}' must include candidate_gcodes to determine printer association.")

                # Append the new component to the product.
                product.components.append(component)

    # Save changes.
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        abort(400, description=str(e))

    return jsonify(product.to_dict()), 200
