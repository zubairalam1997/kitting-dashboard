from django.shortcuts import render
from django.http import JsonResponse ,HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import vc_n_asn ,VcMaster , VcDatabase ,EslPart , AsnSchedule , WorkTable ,trolley_data
import requests
from collections import deque
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Exists, OuterRef ,Q
import time
import json
from itertools import cycle
from django.shortcuts import get_object_or_404

# Assuming your trolley model is `Trolley`


# Define a list of queue colors
seven_queue = ["ff00","ffff00",  "ff", "ff0000", "ff00ff", "ffffff", "00ffff"]

# Function to display the color code
def display_color():
    # Get the first color code from the list
    color_code = seven_queue.pop(0)

    # Add the color code back to the end of the list
    seven_queue.append(color_code)

    # Return the color code
    return color_code

global vc_number
posted_vc = None
#make list for posted vc and then match to it 

@csrf_exempt
def get_combined_data(request):
    qr_data = request.POST.get('qr_data')
    vc_n_asn_data = vc_n_asn.objects.all()
    combined_data = []
    print('combined Data:',qr_data)
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
            'trolley_qr': qr_data,
        }
        combined_data.append(data_entry)
        kitting_in_process_data = [entry for entry in combined_data if entry['vc_number'] == posted_vc]
        print('psted_vc',posted_vc)
    return JsonResponse({'combined_data': combined_data , 'kitting_in_process_data': kitting_in_process_data})

@csrf_exempt
def picking_plan(request):
    global posted_vc
    #vc_n_asn.objects.filter(vcn = posted_vc).delete()
    vc_n_asn_data = vc_n_asn.objects.all()

    # Define a list to store the combined data
    
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
            combined_data = [entry for entry in combined_data if entry['vc_number'] != posted_vc]
            
            #add code to delete the combined data entry if match posted vc
        else:
            # If no matching model found, append a message to the combined_data list
            combined_data.append({
                'vc_number': vc_number,
                'asn_number': asn_number,
                'model': 'No matching model found',
                'plan_date': date_time.date(),
                'schedule_time':date_time.time(),
            })

    
    return render(request, 'pick_plan.html', {'combined_data': combined_data})



@csrf_exempt
def get_Payload_Data(request):
    global posted_vc
    
    global vc_number
    if request.method == 'POST':
        qr_data = request.POST.get('qr_data')
        if qr_data==None:
            vc_number = request.POST.get('vc_number')
        print('thisis :',qr_data, vc_number)
        
    
        try:
            # Check if all trolleys are engaged
            if trolley_data.objects.filter(trolley_picking_status="pending").count() >= 7:
                return JsonResponse({'error': 'All trolleys are currently engaged'}, status=400)
            # Find the matching trolley based on the QR code
            matching_trolley = trolley_data.objects.filter(trolley_code=qr_data).first()

            if matching_trolley:
                # Check if the trolley is already engaged
                if matching_trolley.trolley_picking_status == "pending":
                    return JsonResponse({'error': 'This trolley is already engaged'}, status=400)



            vc_n_asn_data = vc_n_asn.objects.all()
            # Get all VC data objects for the given VC number
            vc_data_list = VcDatabase.objects.filter(vc_no=vc_number)
            # Initialize an empty list to store the data for each part number
            data_list = []

            for vc_data in vc_data_list:
                part_number = vc_data.part_no

                try:
                    # Get the ESL data for the current part number
                    esl_data = EslPart.objects.get(partno=part_number)
                     
                   
                    led_color = display_color()

                    # Append the data for the current part number to the list
                    data_list.append({
                        "Part No.": part_number,
                        "DESC": vc_data.part_desc,
                        "QTY": vc_data.quantity,
                        "mac": esl_data.tagid,
                        "ledstate": "0",  # Default value for ledstate
                        "ledrgb": led_color,
                        "outtime": "0",
                        "styleid": "50",
                        "qrcode": "2001",
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
                    posted_vc = vc_number
                    print('posted_vc',posted_vc)
                    try:
                        vc_n_asn_entry = vc_n_asn.objects.get(vcn=posted_vc)
                        asn_number = vc_n_asn_entry.asnn
                    except vc_n_asn.DoesNotExist:
                        return JsonResponse({'error': 'VC number not found in vc_n_asn'}, status=404)
                    # Query VcMaster to get the model corresponding to the posted VC number
                    try:
                        vc_master_entry = VcMaster.objects.get(vcnumber=posted_vc)
                        model_info = vc_master_entry.model
                    except VcMaster.DoesNotExist:
                        # Handle the case where the VC number is not found in VcMaster
                        return JsonResponse({'error': 'VC number not found in VcMaster'}, status=404)
                    try:
                        # Create AsnSchedule object
                        asn_schedule_created = AsnSchedule.objects.create(vc_no=posted_vc, asn_no=asn_number, model=model_info, start_time=timezone.now(), trqr=qr_data, color=led_color)
                        
                        if asn_schedule_created:
                            # Check if the trqr matches any trolley_code
                            matching_trolley = trolley_data.objects.filter(trolley_code=qr_data).first()
                            trolley_mac=matching_trolley.mac
                            matching_trolley.trolley_picking_status="pending"
                            matching_trolley.save()
                            print('trolley_mac:',trolley_mac)
                            if matching_trolley:
                                # Construct payload for trolley screen update
                                trolley_payload = [
                                {"mac": trolley_mac,"mappingtype":135,"styleid":54,"qrcode":"","Status":"PENDING","MODEL":asn_schedule_created.model,"VC":asn_schedule_created.vc_no,"ASN":asn_schedule_created.asn_no,"ledrgb":led_color,"ledstate":"0","outtime":"0"}]
                                
                                # Send POST request to update trolley screen
                                response = requests.post('http://192.168.1.100/wms/associate/updateScreen', json=trolley_payload)
                                response.raise_for_status()
                            else:
                                return JsonResponse({'error': 'No matching trolley found'}, status=404)  # Return error if no matching trolley found
                        else:
                            return JsonResponse({'error': 'ASN Schedule not created'}, status=500)  # Internal server error if ASN schedule not created

                    except Exception as e:
                        return JsonResponse({'error': str(e)}, status=500)  # Return error response with the exception message

                    for item in data_list:
                        WorkTable.objects.create(
                            tagid=item['mac'],
                            tagcode=item['qrcode'],  # Update with appropriate field
                            tagname=item['mac'],  # Update with appropriate field
                            stdatetime=timezone.now(),
                            partno = item['Part No.'],
                            partdesc = item['DESC'],
                            qty = item['QTY'],
                            asn = asn_number,#store posted asn rrelated to  partnumbers 
                            # Add other fields from data_list as needed
                        )
                        
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
  
def kitting_in_process(request):
    try:
        # Subquery to check if there are any entries with pending status for the same ASN number
        pending_subquery = WorkTable.objects.filter(
            asn=OuterRef('asn'), status='pending'
        )

        # Annotate each ASN number with a flag indicating if any entry has a pending status
        completed_work_table = WorkTable.objects.annotate(
            any_pending=Exists(pending_subquery)
        )
        
        # Filter to get only those ASN numbers where all entries are completed and none has a pending status
        filtered_work_table = completed_work_table.values('asn').annotate(
            completed_count=Count('id', filter=Q(status='completed')),
        ).filter(
            completed_count=Count('id'),
            any_pending=False,
        )

        # Get the distinct ASN numbers from the filtered queryset
        completed_asn_values = [item['asn'] for item in filtered_work_table]
        
        # Filter AsnSchedule objects based on the completed ASN numbers
        kitting_in_process_data = AsnSchedule.objects.exclude(asn_no__in=completed_asn_values).distinct('asn_no')
         
    
    #kitting_in_process_data = AsnSchedule.objects.all()
   

        return render(request, 'kitting_in_process.html', {'kitting_in_process_data': kitting_in_process_data})
    except AsnSchedule.DoesNotExist:
        return render(request, 'kitting_in_process.html', {'kitting_in_process_data': None})
   
@csrf_exempt
def open_modal(request):
    if request.method == 'POST':
        clicked_asn = request.POST.get('asn_number')
        
        # Retrieve the relevant data from the database
        open_modal_data = list(WorkTable.objects.filter(asn=clicked_asn).values('partno', 'partdesc', 'qty','status'))
        
        # Return the data as JSON response
        return JsonResponse(open_modal_data, safe=False)
    
    # Return a JsonResponse even for GET requests with an empty list
    return JsonResponse([], safe=False)
from django.template.loader import render_to_string
from django.http import HttpResponseBadRequest

@csrf_exempt
def render_modal(request):
    if request.method == 'POST':
        data = json.loads(request.POST.get('open_modal_data', '[]'))
        rendered_html = render_to_string('modal.html', {'open_modal_data': data})
        return HttpResponse(rendered_html)
    else:
        return HttpResponseBadRequest('Invalid request method')

    
@require_POST
@csrf_exempt
def enter_key(request):
    print('this is reuest',request)
    if request.method == 'POST':
        data = json.loads(request.body)
        mac_address = data.get('mac')
        
        print('this is mac:',mac_address )
    WorkTable_objects = WorkTable.objects.filter(tagid=mac_address)
    WorkTable_objects.update(status='completed' , eddatetime = timezone.now())
    try:
        # Subquery to check if there are any entries with pending status for the same ASN number
        pending_subquery = WorkTable.objects.filter(
            asn=OuterRef('asn'), status='pending'
        )

        # Annotate each ASN number with a flag indicating if any entry has a pending status
        completed_work_table = WorkTable.objects.annotate(
            any_pending=Exists(pending_subquery)
        )
        
        # Filter to get only those ASN numbers where all entries are completed and none has a pending status
        filtered_work_table = completed_work_table.values('asn').annotate(
            completed_count=Count('id', filter=Q(status='completed')),
        ).filter(
            completed_count=Count('id'),
            any_pending=False,
        )

        # Get the distinct ASN numbers from the filtered queryset
        completed_asn_values = [item['asn'] for item in filtered_work_table]
        
        
        # Filter AsnSchedule objects based on the completed ASN numbers
        completed_picks = AsnSchedule.objects.filter(asn_no__in=completed_asn_values).distinct('asn_no')
            # Iterate over completed picks to update trolley payload status
        completed_trqrs = completed_picks.values_list('trqr', flat=True)
        # Filter trolley_data based on the trqrs from completed picks
        matching_trolleys = trolley_data.objects.filter(trolley_code__in=completed_trqrs)
        # Initialize an empty list to store trolley_mac values
        trolley_macs = []
        # Iterate over matching trolleys, update their status to completed, and collect their mac addresses
        for trolley in matching_trolleys:
            trolley.trolley_picking_status = "completed"
            trolley.save()
            trolley_macs.append(trolley.mac)
        
            try:
                trolley_macs.append(trolley.mac)
                
                # Construct payload for trolley screen update
                for mac in trolley_macs:
                    trolley_payload = [
                                    {"mac": mac,"mappingtype":135,"styleid":54,"qrcode":"","Status":"COMPLETED","MODEL":"pick.model","VC":"pick.vc_no","ASN":"pick.asn_no","ledrgb":"ff07","ledstate":"0","outtime":"3"}
                                    
                                    ]
                                
                # Send POST request to update trolley picking status 
                response = requests.post('http://192.168.1.100/wms/associate/updateScreen', json=trolley_payload)
                response.raise_for_status()
                
            except trolley_data.DoesNotExist:
                # Handle the case where no matching trolley data is found
                pass

        

    except AsnSchedule.DoesNotExist:

   

        return JsonResponse({'message': 'Request processed successfully'}) 



def completed_kittings(request):
    try:
        # Subquery to check if there are any entries with pending status for the same ASN number
        pending_subquery = WorkTable.objects.filter(
            asn=OuterRef('asn'), status='pending'
        )

        # Annotate each ASN number with a flag indicating if any entry has a pending status
        completed_work_table = WorkTable.objects.annotate(
            any_pending=Exists(pending_subquery)
        )
        
        # Filter to get only those ASN numbers where all entries are completed and none has a pending status
        filtered_work_table = completed_work_table.values('asn').annotate(
            completed_count=Count('id', filter=Q(status='completed')),
        ).filter(
            completed_count=Count('id'),
            any_pending=False,
        )

        # Get the distinct ASN numbers from the filtered queryset
        completed_asn_values = [item['asn'] for item in filtered_work_table]
        
        # Filter AsnSchedule objects based on the completed ASN numbers
        completed_picks = AsnSchedule.objects.filter(asn_no__in=completed_asn_values).distinct('asn_no')
         

        return render(request, 'completed_kittings.html', {'completed_picks': completed_picks})
    
    except AsnSchedule.DoesNotExist:
        # Handle the case where no AsnSchedule objects are found
        return render(request, 'completed_kittings.html', {'completed_picks': None})

#USE ASN NUMBER INSTEAD VC NUMBER IF CONDITION NEEDED
#remove posted vc from vcnasn , update light colcor using queue and update status when all sattus updated then put that data in completed kittings and remove it from asn schedule table
