from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import vc_n_asn ,VcMaster , VcDatabase ,EslPart , AsnSchedule , WorkTable
import requests
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

import json

global vc_number


def get_combined_data(request):
    global vc_number
    
    vc_n_asn_data = vc_n_asn.objects.all()
    combined_data = []
    for entry in vc_n_asn_data:
        vc_number = entry.vcn
        asn_number = entry.asnn
        matching_models = VcMaster.objects.filter(vcnumber=vc_number)

        if matching_models.exists():
            model_info = matching_models.first().model
        else:
            model_info = 'No matching model found'

        data_entry = {
            'vc_number': vc_number,
            'asn_number': asn_number,
            'model': model_info,
        }
        combined_data.append(data_entry)
    
    return JsonResponse({'combined_data': combined_data})

@csrf_exempt
def picking_plan(request):
    vc_n_asn_data = vc_n_asn.objects.all()

    # Define a list to store the combined data
    global combined_data
    combined_data = []

    # Iterate over each entry in vc_n_asn_data
    for entry in vc_n_asn_data:
        vc_number = entry.vcn
        asn_number = entry.asnn
        date_time = entry.schedule_date_time

        # Query VcMaster to find matching model for the VC number
        matching_models = VcMaster.objects.filter(vcnumber=vc_number)

        # Check if matching_models is not empty
        if matching_models.exists():
            # Retrieve the first matching model
            model_info = matching_models.first().model

            # Create a dictionary to store VC, ASN, and model information
            data_entry = {
                'vc_number': vc_number,
                'asn_number': asn_number,
                'model': model_info,
                'plan_date': date_time.date(),
                'schedule_time': date_time.time(),
            }

            # Add the dictionary to the combined_data list
            combined_data.append(data_entry)
        else:
            # If no matching model found, append a message to the combined_data list
            combined_data.append({
                'vc_number': vc_number,
                'asn_number': asn_number,
                'model': 'No matching model found',
                'plan_date': date_time.date(),
                'schedule_time':date_time.time(),
            })

    # Render the template with the combined data
        #return JsonResponse({'combined_data': combined_data})
    return render(request, 'pick_plan.html', {'combined_data': combined_data})

def open_modal(request):
    
    return render(request, 'scanner.html' )



def kitting_in_process(request):
    in_process = WorkTable.objects.all()
    return render (request , 'kitting_in_process.html' , {'in_process': in_process})

@csrf_exempt
def get_Payload_Data(request):
    global vc_number
    if request.method == 'POST':
        qr_data = request.POST.get('qr_data')
        if qr_data==None:
            vc_number = request.POST.get('vc_number')
        print('thisis :',qr_data, vc_number)
        
    
        try:
            # Get all VC data objects for the given VC number
            vc_data_list = VcDatabase.objects.filter(vc_no=vc_number)

            # Initialize an empty list to store the data for each part number
            data_list = []

            for vc_data in vc_data_list:
                part_number = vc_data.part_no

                try:
                    # Get the ESL data for the current part number
                    esl_data = EslPart.objects.get(partno=part_number)

                    # Append the data for the current part number to the list
                    data_list.append({
                        "Part No.": part_number,
                        "DESC": vc_data.part_desc,
                        "QTY": vc_data.quantity,
                        "mac": esl_data.tagid,
                        "ledstate": "0",  # Default value for ledstate
                        "ledrgb": "ff00",
                        "outtime": "60",
                        "styleid": "50",
                        "qrcode": qr_data,
                        "mappingtype": "79"
                    })
                except EslPart.DoesNotExist:
                    # Handle if part number not found in ESL model
                    pass

            if data_list and qr_data:
                #print('post_it:',data_list)
                # for tag_id in data_list[tag_id]:
                response = requests.post('http://192.168.1.100/wms/associate/updateScreen', json=data_list)
                response.raise_for_status()
                # # Check if the request was successful
                if response.ok:
                    # Save data_list data to WorkTable model
                    for item in data_list:
                        WorkTable.objects.create(
                            tagid=item['mac'],
                            tagcode=item['qrcode'],  # Update with appropriate field
                            tagname=item['mac'],  # Update with appropriate field
                            stdatetime=timezone.now(),
                            partno = item['Part No.'],
                            partdesc = item['DESC'],
                            qty = item['QTY'],
                            
                            # Add other fields from data_list as needed
                        )
                         # Remove the entry from combined_data if vc_number matches
                    combined_data = json.loads(request.session.get('combined_data', '[]'))
                    combined_data = [entry for entry in combined_data if entry['vc_number'] != vc_number]
                    request.session['combined_data'] = json.dumps(combined_data)
                    return JsonResponse({'success': 'Data posted successfully'})
                else:
                    return JsonResponse({'error': 'Failed to post data'}, status=500)
            
                return JsonResponse(data_list, safe=False)
            else:
                return JsonResponse({'error': 'No matching part numbers found in ESL model'}, status=404)

        except VcDatabase.DoesNotExist:
            return JsonResponse({'error': 'VC number not found'}, status=404)

    else:
        return JsonResponse({'error': 'Invalid request'}, status=400)

    #NOW EXTRACT PART NUMBER FROM THIS AND MATCH IT IN ESL AND POST DATA ON THAT MAC BEFORE THIS MAKE A POSTDATA FUNCTION 
