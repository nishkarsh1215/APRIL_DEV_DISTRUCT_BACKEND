import razorpay
import os
from helpers.auth_helper import token_required
from flask_restx import Namespace as RestxNamespace, Resource, fields
import sys
from flask import request

order_ns = RestxNamespace('order', description='HTTP-based order endpont')

RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')

order_model = order_ns.model('Order', {
    'amount': fields.Integer(example=5),
    'currency': fields.String(example="INR")
})

client = razorpay.Client(auth=("rzp_live_rgk9Ll05p1Ehl5", "zLhkks5UL8Od6XdaqYMjA838"))

@order_ns.route('/create')
class CreateOrder(Resource):
    @order_ns.doc(security='apikey')
    @token_required
    # @order_ns.expect(order_model, validate=True)
    def post(self, user):
        """
        Create an order with Razorpay.
        """
        # Log the headers for debugging
        print(f"Request headers: {dict(request.headers)}", flush=True)
        sys.stdout.flush()
        
        amount=request.form.get("amount")
        
        print(f"Creating order for user {user.id} with amount: {amount}", flush=True)
        sys.stdout.flush()
        
        if not amount:
            return {'error': 'Amount is required'}, 400
        
        try:
            order_data = { "amount": int(amount) * 85, "currency": "INR", "receipt": "order_rcptid_11" }
            order = client.order.create(data=order_data)
            
            if int(amount) == 20:
                user.plan = "Basic"
                user.freeCredits = 10000000 
            elif int(amount) == 50:
                user.plan = "Pro"
                user.freeCredits = 25000000
            elif int(amount) == 100:
                user.plan = "Ultimate"
                user.freeCredits = 75000000
            
            # Store the order ID with the user
            if not hasattr(user, 'orderIds'):
                user.orderIds = []
            user.orderIds.append(order['id'])
            user.save()
            
            return {'order_id': order['id'], 'amount': order['amount'], 'plan': user.plan}, 201
        except Exception as e:
            print(f"Error creating order: {str(e)}", flush=True)
            return {'error': str(e)}, 500

@order_ns.route('/verify')
class VerifyOrder(Resource):
    @token_required
    def post(self, user):
        razorpay_order_id = request.form.get('razorpay_order_id')
        razorpay_payment_id = request.form.get('razorpay_payment_id')
        razorpay_signature = request.form.get('razorpay_signature')
        
        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return {'error': 'All fields are required'}, 400
        
        try:
            # Verify the payment signature
            client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
            
            return {'message': 'Payment verified successfully'}, 200
        except Exception as e:
            return {'error': str(e)}, 500