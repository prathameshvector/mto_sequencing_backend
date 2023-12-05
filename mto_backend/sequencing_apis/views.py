from django.shortcuts import render
import csv
import json
import pandas as pd
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
# Create your views here.
@csrf_exempt
@require_POST
@csrf_exempt
@require_POST
def process_data(request):
    # Handle XLSX file
    if 'xlsx_file' in request.FILES:
        xlsx_file = request.FILES['xlsx_file']

        # Read XLSX file using pandas
        df = pd.read_excel(xlsx_file)

        # Process XLSX data (example: print the DataFrame)
        print(df)

    # Handle JSON data
    if 'json_data' in request.POST:
        json_data = json.loads(request.POST['json_data'])

        # Process JSON data (example: print the JSON data)
        print(json_data)

        # You can customize the response based on your requirements
        return JsonResponse({'message': 'Data processed successfully'})


def index(request):
    return render(request, 'index.html')