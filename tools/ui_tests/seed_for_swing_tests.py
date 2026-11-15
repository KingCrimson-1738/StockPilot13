import requests
B="http://127.0.0.1:8000"
reg=lambda e,n: requests.post(f"{B}/auth/register",json={"email":e,"full_name":n,"password":"password123"}).json()
o=reg("asha@example.com","Asha Kumar"); s=reg("ravi@example.com","Ravi Staff")
h={"Authorization":"Bearer "+o["access_token"]}
b=requests.post(f"{B}/businesses",json={"name":"ABC Electronics","default_min_stock":5},headers=h).json()
requests.post(f"{B}/businesses",json={"name":"ABC Furniture"},headers=h)
requests.post(f"{B}/businesses/{b['id']}/members",json={"email":"ravi@example.com"},headers=h)
cat=requests.post(f"{B}/businesses/{b['id']}/categories",json={"name":"Cables"},headers=h).json()
p=lambda body: requests.post(f"{B}/businesses/{b['id']}/products",json=body,headers=h)
requests.post(f"{B}/businesses/{b['id']}/suppliers",json={"name":"Volt Traders","contact_person":"Meena","phone":"9999999999"},headers=h)
p({"name":"USB-C Cable","sku":"CBL-1","category_id":cat["id"],"opening_quantity":50,"purchase_price":"100","selling_price":"250"})
p({"name":"Phone X","sku":"PH-X","opening_quantity":3,"purchase_price":"1000","selling_price":"1500"})
p({"name":"Charger","sku":"CHG-1","opening_quantity":0,"purchase_price":"50","selling_price":"80"})
print("seeded")
