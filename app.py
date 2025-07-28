from markupsafe import escape
from flask import Flask, session, request, redirect, url_for, render_template, flash, get_flashed_messages, jsonify

app = Flask(__name__)

# Set the secret key to some random bytes. Keep this really secret!
app.secret_key = b'jd7E7nd0882nao*##\t'

users = {}
admin_credentials = {
    'admin': 'Admin@254#'  
}

def read_recipe_file(filename):
    recipe_dictionary = {}
    with open(filename, encoding='utf-8') as recipeFile:
        for row in recipeFile:
            row = row.strip()
            if not row:
                continue
            try:
                name_price, ingredients_str = row.split(":")
                name, price = name_price.strip().split("|")
                ingredients = [ingredient.strip() for ingredient in ingredients_str.strip().split()]
                recipe_dictionary[name.lower()] = {
                    "price": int(price),
                    "ingredients": ingredients
                }
            except ValueError as e:
                print(f"Skipping invalid line: {row} → {e}")
    return recipe_dictionary

recipes = read_recipe_file("static/data/recipes.txt")

# FIXED: Clear session data properly on logout/login
def clear_user_session():
    """Clear all user-specific session data"""
    session.pop('cart', None)
    session.pop('username', None)
    session.pop('clear_once', None)
    session.modified = True

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/menu')
def show_menu():
    return render_template("menu.html", pizzas=recipes)

@app.route('/menu/<pizza_name>')
def show_pizza(pizza_name):
    # only pass the list of ingredients
    if pizza_name.lower() not in recipes:
        flash("Pizza not found!")
        return redirect(url_for('show_menu'))
    return render_template('pizza.html', pizza=pizza_name, ingredients=recipes[pizza_name.lower()]["ingredients"])

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        # Validation
        if not username or not password:
            flash("Username and password are required!")
            return redirect(url_for('signup'))
            
        if username in users:
            flash("Username already exists!")
            return redirect(url_for('signup'))
            
        # Create new user
        users[username] = {'password': password}
        
        # FIXED: Clear any existing session data before login
        clear_user_session()
        session['username'] = username
        flash(f"Welcome {username}! Account created successfully.")
        return redirect(url_for('index'))
    return render_template("signup.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if not username or not password:
            return render_template("login.html", message="Username and password are required!")
            
        if username not in users:
            return render_template("login.html", message="Incorrect username!")
        elif users[username]['password'] != password:
            return render_template("login.html", message="Incorrect password!")
        else:
            # FIXED: Clear any existing session data before login
            clear_user_session()
            session['username'] = username
            flash(f"Welcome back, {username}!")
            return redirect(url_for('index'))
    else:
        return render_template("login.html")

@app.route('/logout')
def logout():
    username = session.get('username', 'User')
    # FIXED: Properly clear all session data
    clear_user_session()
    flash(f"Goodbye {username}! You have been logged out.")
    return redirect(url_for('index'))

# Admin routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if username in admin_credentials and admin_credentials[username] == password:
            session['admin'] = username
            flash("Admin login successful!")
            return redirect(url_for('admin_panel'))
        else:
            flash("Invalid admin credentials")
            return redirect(url_for('admin_login'))
    return render_template('admin_login.html')

@app.route('/admin/panel')
def admin_panel():
    if 'admin' not in session:
        flash("You must be logged in as admin to access the admin panel.")
        return redirect(url_for('admin_login'))
    return render_template("admin_panel.html", users=users)

@app.route('/admin/logout')
def admin_logout():
    admin_name = session.get('admin', 'Admin')
    session.pop('admin', None)
    session.modified = True
    flash(f"Logged out from admin panel as {admin_name}.")
    return redirect(url_for('index'))

# Cart routes - FIXED AND ENHANCED
@app.route('/cart')
def view_cart():
    if 'username' not in session:
        flash("Please login to view your cart.")
        return redirect(url_for('login'))
        
    cart = session.get('cart', {})
    cart_items = []
    total = 0

    for name, quantity in cart.items():
        recipe = recipes.get(name.lower())
        if recipe:
            price = recipe['price']
            cart_items.append({
                'name': name.title(),
                'price': price,
                'quantity': quantity,
                'subtotal': price * quantity
            })
            total += price * quantity

    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'username' not in session:
        flash("Please login to add items to cart.")
        return redirect(url_for('login'))
        
    pizza_name = request.form.get('item', '').strip().lower()

    if not pizza_name or pizza_name not in recipes:
        flash("Invalid pizza selection!")
        return redirect(url_for('show_menu'))

    # Initialize cart
    cart = session.get('cart', {})

    # Update cart
    cart[pizza_name] = cart.get(pizza_name, 0) + 1
    session['cart'] = cart
    session.modified = True
    
    flash(f"{pizza_name.title()} added to cart!")
    return redirect(url_for('view_cart'))

# NEW: Remove item from cart
@app.route('/remove_from_cart/<pizza_name>')
def remove_from_cart(pizza_name):
    if 'username' not in session:
        flash("Please login to modify your cart.")
        return redirect(url_for('login'))
        
    cart = session.get('cart', {})
    pizza_name = pizza_name.lower()
    
    if pizza_name in cart:
        del cart[pizza_name]
        session['cart'] = cart
        session.modified = True
        flash(f"{pizza_name.title()} removed from cart!")
    else:
        flash("Item not found in cart!")
        
    return redirect(url_for('view_cart'))

# NEW: Update cart quantity via AJAX
@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Please login first'})
        
    data = request.get_json()
    pizza_name = data.get('item', '').strip().lower()
    new_quantity = int(data.get('quantity', 1))
    
    if not pizza_name or pizza_name not in recipes:
        return jsonify({'success': False, 'message': 'Invalid item'})
    
    cart = session.get('cart', {})
    
    if new_quantity <= 0:
        cart.pop(pizza_name, None)
    else:
        cart[pizza_name] = new_quantity
        
    session['cart'] = cart
    session.modified = True
    
    # Calculate new totals
    total = 0
    for name, qty in cart.items():
        if name in recipes:
            total += recipes[name]['price'] * qty
    
    return jsonify({
        'success': True, 
        'cart': cart, 
        'total': total,
        'item_count': sum(cart.values())
    })

# NEW: Apply coupon code
@app.route('/apply_coupon', methods=['POST'])
def apply_coupon():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Please login first'})
        
    data = request.get_json()
    coupon_code = data.get('code', '').strip().upper()
    
    # Sample coupons - you can expand this
    valid_coupons = {
        'PIZZA10': {'type': 'percentage', 'value': 10, 'name': '10% off'},
        'NEWUSER': {'type': 'fixed', 'value': 100, 'name': 'Ksh 100 off'},
        'STUDENT': {'type': 'percentage', 'value': 15, 'name': '15% student discount'}
    }
    
    if coupon_code in valid_coupons:
        session['applied_coupon'] = valid_coupons[coupon_code]
        session.modified = True
        return jsonify({'success': True, 'coupon': valid_coupons[coupon_code]})
    else:
        return jsonify({'success': False, 'message': 'Invalid coupon code'})

# NEW: Clear cart
@app.route('/clear_cart')
def clear_cart():
    if 'username' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))
        
    session.pop('cart', None)
    session.pop('applied_coupon', None)
    session.modified = True
    flash("Cart cleared successfully!")
    return redirect(url_for('view_cart'))

# Checkout route - ENHANCED
@app.route('/checkout')
def checkout():
    print(f"Session data: {session}")  # Debug line
    print(f"Username in session: {'username' in session}")  # Debug line
    
    if 'username' not in session:
        print("Redirecting to login - no username in session")  # Debug line
        flash("Please login to checkout.")
        return redirect(url_for('login'))
        
    cart = session.get('cart', {})
    print(f"Cart contents: {cart}")  # Debug line
    
    if not cart:
        print("Redirecting to menu - empty cart")  # Debug line
        flash("Your cart is empty!")
        return redirect(url_for('show_menu'))
        
    # Calculate totals
    subtotal = 0
    for name, quantity in cart.items():
        if name in recipes:
            subtotal += recipes[name]['price'] * quantity
    
    # Apply coupon discount
    coupon = session.get('applied_coupon')
    discount = 0
    if coupon:
        if coupon['type'] == 'percentage':
            discount = subtotal * (coupon['value'] / 100)
        else:
            discount = coupon['value']
    
    delivery_fee = 150
    tax = (subtotal - discount) * 0.16
    total = subtotal + delivery_fee + tax - discount
    
    return render_template('checkout.html', 
                         cart=cart, 
                         subtotal=subtotal,
                         discount=discount,
                         delivery_fee=delivery_fee,
                         tax=tax,
                         total=total,
                         coupon=coupon)
# REMOVED: The problematic clear_cart_once function that was causing issues
# @app.before_request - This was clearing cart unexpectedly

# NEW: Get cart count for navigation
@app.route('/cart_count')
def get_cart_count():
    if 'username' not in session:
        return jsonify({'count': 0})
        
    cart = session.get('cart', {})
    count = sum(cart.values())
    return jsonify({'count': count})

# FIXED: Home route (was conflicting with index)
@app.route('/home')
def home():
    return redirect(url_for('index'))

# NEW: API endpoint to get cart contents
@app.route('/api/cart')
def api_cart():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
        
    cart = session.get('cart', {})
    cart_data = []
    total = 0
    
    for name, quantity in cart.items():
        recipe = recipes.get(name)
        if recipe:
            price = recipe['price']
            subtotal = price * quantity
            cart_data.append({
                'name': name.title(),
                'price': price,
                'quantity': quantity,
                'subtotal': subtotal
            })
            total += subtotal
    
    return jsonify({
        'items': cart_data,
        'total': total,
        'count': sum(cart.values())
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    flash("Page not found!")
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(error):
    flash("An internal error occurred!")
    return redirect(url_for('index'))

#about
@app.route('/about')
def about():
    return redirect(url_for('about'))

if __name__ == '__main__':
    app.run(debug=True)