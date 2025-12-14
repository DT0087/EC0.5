from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

import os

# --- Flask アプリケーション設定 ---

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # セッション用


# --- ファイルアップロード設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# --- MySQL 接続設定 ---
# グローバルな接続を避け、リクエストごとに新しい接続を取得するための関数
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="hewv1"
    )


# ---ホームページ---
@app.route('/')
def home():
    return render_template('index.html')

# # --- 商品一覧（検索対応） ---
# @app.route('/items', methods=['GET'])
# def items_list():
#     keyword = request.args.get('q', '')  # 検索ワード

#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)

#     if keyword:
#         sql = "SELECT * FROM item WHERE name LIKE %s OR description LIKE %s"
#         cursor.execute(sql, [f"%{keyword}%", f"%{keyword}%"])
#     else:
#         sql = "SELECT * FROM item"
#         cursor.execute(sql)

#     items = cursor.fetchall()
#     cursor.close()
#     conn.close()

#     return render_template('items_list.html', items=items, keyword=keyword)

# --- 新規会員登録 ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        email_confirm = request.form['email_confirm']
        password_raw = request.form['password']
        password_confirm = request.form['password_confirm']

        # --- メールアドレス一致チェック ---
        if email != email_confirm:
            flash('メールアドレスが一致しません。', 'error')
            return redirect(url_for('register'))

        # --- パスワード一致チェック ---
        if password_raw != password_confirm:
            flash('パスワードが一致しません。', 'error')
            return redirect(url_for('register'))

        # --- パスワードハッシュ生成 ---
        password = generate_password_hash(password_raw)

        # --- DB 接続 ---
        conn = get_db_connection()
        cursor = conn.cursor()

        # ★ 5桁ID生成 ★
        new_id = generate_5digit_id(conn)

        # --- DB登録 ---
        sql = "INSERT INTO users (id, username, email, password) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (new_id, username, email, password))

        conn.commit()
        cursor.close()
        conn.close()

        flash('登録が完了しました！ログインしてください。', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# --- ログイン機能 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection() # 修正
        cursor = conn.cursor(dictionary=True) # 修正
        sql = "SELECT * FROM users WHERE email = %s"
        cursor.execute(sql, (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close() # 修正

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('ログイン成功！', 'success')
            return redirect(url_for("mypage"))
        else:
            flash('メールアドレスまたはパスワードが違います', 'danger')
    
    return render_template('login.html')

# --- 5桁ID生成関数 ---
def generate_5digit_id(conn):
    cursor = conn.cursor()

    # 現在の最大IDを取得
    cursor.execute("SELECT MAX(id) FROM users")
    result = cursor.fetchone()[0]

    if result:
        next_num = int(result) + 1
    else:
        next_num = 1

    # 5桁ゼロ埋め
    return f"{next_num:05d}"


# --- ログアウト ---
@app.route('/logout')
def logout():
    session.clear()
    flash('ログアウトしました', 'info')
    return redirect(url_for('login'))

# --- 商品一覧 ---
@app.route('/items')
def items_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection() # 修正
    cursor = conn.cursor(dictionary=True) # 修正: dictionary=True を追加
    cursor.execute("SELECT * FROM item")
    items = cursor.fetchall()
    # 依頼一覧の取得は/dependenciesに任せるため削除（任意）
    cursor.execute("SELECT * FROM dependency")
    dependencies = cursor.fetchall()
    cursor.close()
    conn.close() # 修正

    return render_template('items.html', items=items, dependencies=dependencies)

# --- 商品詳細ページ ---
@app.route('/item/<int:item_id>')
def item_detail(item_id):
    conn = get_db_connection() # 修正
    cursor = conn.cursor(dictionary=True) # 修正
    cursor.execute("SELECT * FROM item WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    cursor.close()
    conn.close() # 修正

    if not item:
        return "商品が見つかりません", 404

    return render_template('item_detail.html', item=item)

# --- カートに追加 ---
@app.route('/cart/add/<int:item_id>')
def add_to_cart(item_id):
    if 'cart' not in session:
        session['cart'] = []

    # IDをカートに追加
    session['cart'].append(item_id)
    session.modified = True
    flash('カートに商品を追加しました', 'success')
    return redirect(url_for('show_cart'))


# --- カート表示 ---
@app.route('/cart')
def show_cart():
    item_ids = session.get('cart', [])
    dependency_ids = session.get('dependency_cart', [])

    items = []
    dependencies = []

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 商品を取得
    if item_ids:
        placeholders = ",".join(["%s"] * len(item_ids))
        sql = f"SELECT * FROM item WHERE id IN ({placeholders})"
        cursor.execute(sql, item_ids)
        items = cursor.fetchall()

    # 依頼を取得
    if dependency_ids:
        placeholders = ",".join(["%s"] * len(dependency_ids))
        sql = f"SELECT * FROM dependency WHERE id IN ({placeholders})"
        cursor.execute(sql, dependency_ids)
        dependencies = cursor.fetchall()

    cursor.close()
    conn.close()

    # 合計金額
    total_price = (
        sum(item['price'] for item in items)
        + sum(dep['price'] for dep in dependencies)
    )

    return render_template(
        'cart.html',
        items=items,
        dependencies=dependencies,
        total_price=total_price
    )


# --- カートから削除 ---
# @app.route('/cart/remove/<int:item_id>')
# def remove_from_cart(item_id):
#     if 'cart' in session and item_id in session['cart']:
#         session['cart'].remove(item_id)
#         session.modified = True
#         flash('カートから商品を削除しました', 'success')
#     return redirect(url_for('show_cart'))

@app.route("/remove_from_cart/<item_type>/<int:item_id>")
def remove_from_cart(item_type, item_id):

    if item_type == "item":
        cart = session.get("cart", [])
        if item_id in cart:
            cart.remove(item_id)
            session['cart'] = cart

    elif item_type == "dependency":
        dep_cart = session.get("dependency_cart", [])
        if item_id in dep_cart:
            dep_cart.remove(item_id)
            session['dependency_cart'] = dep_cart

    session.modified = True
    return redirect(url_for('show_cart'))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("ログインが必要です", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# カート画面から決済ページへ
@app.route('/checkout')
@login_required
def checkout():
    item_ids = session.get('cart', [])
    dependency_ids = session.get('dependency_cart', [])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    items = []
    dependencies = []

    if item_ids:
        placeholders = ",".join(["%s"] * len(item_ids))
        cursor.execute(f"SELECT * FROM item WHERE id IN ({placeholders})", item_ids)
        items = cursor.fetchall()

    if dependency_ids:
        placeholders = ",".join(["%s"] * len(dependency_ids))
        cursor.execute(f"SELECT * FROM dependency WHERE id IN ({placeholders})", dependency_ids)
        dependencies = cursor.fetchall()

    cursor.close()
    conn.close()

    total_price = sum([i['price'] for i in items]) + sum([d['price'] for d in dependencies])

    return render_template('checkout.html',
                           items=items,
                           dependencies=dependencies,
                           total_price=total_price)


# 決済処理（ダミー）
@app.route('/process_payment', methods=['POST'])
@login_required
def process_payment():
    user_id = session['user_id']

    card_name = request.form.get('card_name')
    card_number = request.form.get('card_number')
    expiry = request.form.get('expiry')
    cvc = request.form.get('cvc')

    # ここでStripeやPayJPなどの決済APIに送る
    # 今回はテスト用なので簡易的に成功扱い
    success = True

    if success:
        # 決済成功 → カートを空にする
        session.pop('cart', None)
        session.pop('dependency_cart', None)
        session.modified = True

        flash('お支払いが完了しました。ありがとうございました！', 'success')
        return redirect(url_for('items_list'))
    else:
        flash('決済に失敗しました。もう一度お試しください。', 'error')
        return redirect(url_for('checkout'))



# --- 商品追加フォーム ---
@app.route('/item/add', methods=['GET', 'POST'])
def add_item():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        desc = request.form['description']
        price = request.form['price']
        image = request.files['image']

        # --- 画像保存 ---
        filename = secure_filename(image.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(save_path)

        # static 内からの相対パスで保存
        image_url = f"uploads/{filename}"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO item (name, description, price, image_url) VALUES (%s, %s, %s, %s)",
            (name, desc, price, image_url)
        )
        new_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()

        flash(f'{name} を商品として追加しました', 'success')
        return redirect(url_for('item_detail', item_id=new_id))

    return render_template('item_add.html')


# --- 依頼一覧 ---
@app.route('/dependencies')
def dependencies_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection() # 修正
    cursor = conn.cursor(dictionary=True) # 修正
    cursor.execute("SELECT * FROM dependency")
    dependencies = cursor.fetchall()
    cursor.close()
    conn.close() # 修正

    return render_template('dependencies.html', dependencies=dependencies)

# --- 依頼詳細ページ ---
@app.route('/dependency/<int:dependency_id>')
def dependency_detail(dependency_id):
    conn = get_db_connection() # 修正
    cursor = conn.cursor(dictionary=True) # 修正
    cursor.execute("SELECT * FROM dependency WHERE id = %s", (dependency_id,))
    dependency = cursor.fetchone()
    cursor.close()
    conn.close() # 修正

    if not dependency:
        return "依頼が見つかりません", 404

    return render_template('dependency_detail.html', dependency=dependency) 

# --- 依頼をカートに追加 ---
@app.route('/cart/dependency/add/<int:dependency_id>')
def add_dependency_to_cart(dependency_id):
    if 'dependency_cart' not in session:
        session['dependency_cart'] = []

    session['dependency_cart'].append(dependency_id)
    session.modified = True
    flash('依頼をカートに追加しました', 'success')
    return redirect(url_for('show_cart'))

# ---依頼追加フォーム---
@app.route('/dependencies/add', methods=['GET', 'POST'])
def add_dependency():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        image = request.files.get('image')

        image_url = None

        # 画像がある場合のみ保存
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(path)
            image_url = f"uploads/{filename}"
        else:
            image_url = "uploads/noimage.png"  # ← 代替画像を用意してもOK

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO dependency (name, description, price, image_url) VALUES (%s, %s, %s, %s)",
            (name, description, price, image_url)
        )

        conn.commit()
        cursor.close()
        conn.close()

        flash(f'{name} の依頼を追加しました', 'success')
        return redirect(url_for('dependencies_list'))

    return render_template('add_dependency.html')


# --- マイページ ---
@app.route("/mypage")
def mypage():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE id = %s", (session["user_id"],))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        flash("ユーザー情報が見つかりません", "error")
        session.clear()
        return redirect(url_for("login"))

    return render_template("mypage.html", user=user)

# --- ログイン必須 ---
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("ログインが必要です", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# --- 管理者権限デコレーター ---
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT is_admin FROM users WHERE id = %s", (session["user_id"],))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user or user.get("is_admin") != 1:
            flash("管理者権限が必要です", "error")
            return redirect(url_for("mypage"))

        return f(*args, **kwargs)
    return wrapper




# --- 管理者権限デコレーター ---
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT is_admin FROM users WHERE id = %s", (session["user_id"],))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user or user.get("is_admin") != 1:
            flash("管理者権限が必要です", "error")
            return redirect(url_for("mypage"))

        return f(*args, **kwargs)
    return wrapper


# --- 管理者用商品一覧ページ ---
@app.route('/admin/items')
@admin_required
def admin_items():

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM item")
        items = cur.fetchall()

        return render_template('admin_item.html', items=items)

    except Exception as e:
        print(f"Error while fetching items: {e}")
        return "内部エラーが発生しました。", 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# --- 管理者用商品編集ページ ---
@app.route("/admin/item/edit/<int:item_id>", methods=["GET", "POST"])
@admin_required
def edit_item(item_id):

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        item_name = request.form["item_name"]
        base_price = request.form["base_price"]
        description = request.form["description"]

        cur.execute("""
            UPDATE item
            SET name=%s, description=%s, price=%s
            WHERE id=%s
        """, (item_name, description, base_price, item_id))

        conn.commit()

        cur.close()
        conn.close()

        flash("商品を更新しました", "success")
        # 🔥 修正
        return redirect(url_for("admin_items"))

    # GET の場合 → 編集する商品の情報を取得
    cur.execute("SELECT * FROM item WHERE id=%s", (item_id,))
    item = cur.fetchone()

    cur.close()
    conn.close()

    if not item:
        flash("編集対象の商品が見つかりません", "error")
        # 🔥 修正
        return redirect(url_for("admin_items"))

    return render_template("edit_item.html", item=item)


# --- 管理者用商品削除 ---
@app.route("/admin/item/delete/<int:item_id>")
@admin_required
def delete_item(item_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM item WHERE id=%s", (item_id,))
    conn.commit()

    cur.close()
    conn.close()

    flash("商品を削除しました", "success")

    # 🔥 修正
    return redirect(url_for("admin_items"))


# --- 管理者用依頼一覧ページ ---
@app.route('/admin/dependencys')
@admin_required
def admin_dependency():

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM dependency")
    dependencies = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('admin_dependency.html', dependencies=dependencies)

# --- 管理者用依頼削除 ---
@app.route('/admin/dependency/delete/<int:dependency_id>')
@admin_required
def delete_dependency(dependency_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM dependency WHERE id=%s", (dependency_id,))
    conn.commit()

    cur.close()
    conn.close()

    flash("依頼を削除しました", "success")
    return redirect(url_for('admin_dependency'))

# アイコン保存フォルダ
ICON_FOLDER = os.path.join(BASE_DIR, "static", "icons")

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user_id = session["user_id"]

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")

        icon_file = request.files.get("icon")  # ← KeyError 防止

        conn = get_db_connection()
        cur = conn.cursor()

        # 1. アイコン更新（ファイルがある場合だけ）
        if icon_file and icon_file.filename != "":
            filename = secure_filename(icon_file.filename)
            save_path = os.path.join("static/icons", filename)
            icon_file.save(save_path)

            cur.execute("UPDATE users SET icon=%s WHERE id=%s", (filename, user_id))

        # 2. 名前とメール更新
        cur.execute("""
            UPDATE users SET username=%s, email=%s WHERE id=%s
        """, (username, email, user_id))

        conn.commit()
        cur.close()
        conn.close()

        # ★ ここを忘れると表示が変わらない！
        session['username'] = username
        session['email'] = email

        return redirect(url_for("mypage"))

    # GET の場合：今のユーザー情報を表示
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    return render_template("edit_profile.html", user=user)

if __name__ == '__main__':
    app.run(debug=True)