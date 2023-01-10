from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated

from rest_framework.decorators import (
    authentication_classes,
    permission_classes,
    api_view,
)
from rest_framework import status
from rest_framework.response import Response
from django.http import QueryDict

from iSkyLIMS_core.models import (
    SampleProjects,
    SampleProjectsFields,
    LabRequest,
    Samples,
)

from iSkyLIMS_wetlab.models import SamplesInProject

from .serializers import (
    CreateSampleSerializer,
    CreateProjectDataSerializer,
    SampleProjectFieldSerializer,
    SampleSerializer,
    SampleParameterSerializer,
    LabRequestSerializer,
    SampleRunInfoSerializers,
)

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .utils.lab_request_handling import get_laboratory_instance

from .utils.sample_request_handling import (
    collect_statistics_information,
    include_instances_in_sample,
    include_coding,
    get_sample_fields,
    samples_match_on_parameter,
    split_sample_data,
    summarize_samples,
)

"""
stats = openapi.Parameter(
    "project",
    openapi.IN_QUERY,
    description="Project name to fetch the statistics utilization fields. Example Relecov",
    type=openapi.TYPE_STRING,
)
"""

sample_project_fields = openapi.Parameter(
    "project",
    openapi.IN_QUERY,
    description="Project name to fetch the sample project fields defined. Example Relecov",
    type=openapi.TYPE_STRING,
)

sample_fields = openapi.Parameter(
    "project",
    openapi.IN_QUERY,
    description="Fetch the sample fields",
    type=openapi.TYPE_STRING,
)

laboratory = openapi.Parameter(
    "laboratory",
    openapi.IN_QUERY,
    description="Laboratory name form to fetch contact information. Example Harlem Hospital Center",
    type=openapi.TYPE_STRING,
)

sample_in_run = openapi.Parameter(
    "samples",
    openapi.IN_QUERY,
    description="Sample name list to fetch run information",
    type=openapi.TYPE_STRING,
)

sample_state = openapi.Parameter(
    "sampleState",
    openapi.IN_QUERY,
    description="Filter result to the sample which are in this state",
    type=openapi.TYPE_STRING,
)

start_date = openapi.Parameter(
    "startDate",
    openapi.IN_QUERY,
    description="Start date from starting collecting samples",
    type=openapi.TYPE_STRING,
)

end_date = openapi.Parameter(
    "endDate",
    openapi.IN_QUERY,
    description="Start date from starting collecting samples",
    type=openapi.TYPE_STRING,
)

sample_parameter = openapi.Parameter(
    "sampleParameter",
    openapi.IN_QUERY,
    description="Get the samples grouped by the parameter",
    type=openapi.TYPE_STRING,
)

region = openapi.Parameter(
    "region",
    openapi.IN_QUERY,
    description="Filter the samples for the selected region",
    type=openapi.TYPE_STRING,
)

sample_list = openapi.Parameter(
    "samples",
    openapi.IN_QUERY,
    description="List of samples to collect information",
    type=openapi.TYPE_STRING,
)

sample_information = openapi.Parameter(
    "sample",
    openapi.IN_QUERY,
    description="Fecthing information from sample",
    type=openapi.TYPE_STRING,
)

sample_parameter = openapi.Parameter(
    "parameter",
    openapi.IN_QUERY,
    description="Fecthing only parameter information from sample",
    type=openapi.TYPE_STRING,
)


sample_project_name = openapi.Parameter(
    "sample_project_name",
    openapi.IN_QUERY,
    description="Sample Project Name",
    type=openapi.TYPE_STRING,
)

project_fields = openapi.Parameter(
    "project_field",
    openapi.IN_QUERY,
    description="Project fields to make the query. Maximum number of fiels are 2",
    type=openapi.TYPE_STRING,
)

sample_project_field = openapi.Parameter(
    "sample_project_field",
    openapi.IN_QUERY,
    description="Name of the sample project Field. Requires project_name",
    type=openapi.TYPE_STRING,
)


@swagger_auto_schema(
    method="post",
    operation_description="Create a new sample Data in iSkyLIMS",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "sample": openapi.Schema(
                type=openapi.TYPE_STRING, description="Sample name"
            ),
            "sampleState": openapi.Schema(
                type=openapi.TYPE_STRING, description="Sample state"
            ),
            "patientCore": openapi.Schema(
                type=openapi.TYPE_STRING, description="Code assigned to the patient"
            ),
            "labRequest": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Laboratory that request the sample",
            ),
            "sampleType": openapi.Schema(
                type=openapi.TYPE_STRING, description="Type of the sample"
            ),
            "species": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Specie that the sample belongs to",
            ),
            "sampleLocation": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Location where the sample is stored",
            ),
            "sampleEntryDate": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Date when sample is received in the lab",
            ),
            "sampleCollectionDate": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Date when the sample is collected from the specimen",
            ),
            "onlyRecorded": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Select if sample is just recorded or if DNA/RNA manipulation will be done in the lab ",
            ),
            "project": openapi.Schema(
                type=openapi.TYPE_STRING, description="Project name"
            ),
        },
    ),
    responses={
        201: "Successful create information",
        400: "Bad Request",
        500: "Internal Server Error",
    },
)
@authentication_classes([SessionAuthentication, BasicAuthentication])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_sample_data(request):
    if request.method == "POST":
        data = request.data
        if isinstance(data, QueryDict):
            data = data.dict()
        if "sampleName" not in data and "sampleProject" not in data:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if Samples.objects.filter(sampleName__iexact=data["sampleName"]).exists():
            error = {"ERROR": "sample already defined"}
            return Response(error, status=status.HTTP_400_BAD_REQUEST)
        split_data = split_sample_data(data)
        if not isinstance(split_data, dict):
            return Response(split_data, status=status.HTTP_400_BAD_REQUEST)
        apps_name = __package__.split(".")[0]
        inst_req_sample = include_instances_in_sample(
            split_data["s_data"], split_data["lab_data"], apps_name
        )
        if not isinstance(inst_req_sample, dict):
            return Response(inst_req_sample, status=status.HTTP_400_BAD_REQUEST)
        split_data["s_data"] = inst_req_sample
        split_data["s_data"]["sampleUser"] = request.user.pk
        # Adding coding for sample
        split_data["s_data"].update(
            include_coding(request.user.username, split_data["s_data"]["sampleName"])
        )
        sample_serializer = CreateSampleSerializer(data=split_data["s_data"])
        if not sample_serializer.is_valid():
            return Response(
                sample_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        new_sample_id = sample_serializer.save().get_sample_id()
        for d_field in split_data["p_data"]:
            d_field["sample_id"] = new_sample_id
            s_project_serializer = CreateProjectDataSerializer(data=d_field)
            if not s_project_serializer.is_valid():
                return Response(
                    s_project_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )
            s_project_serializer.save()

        return Response("Successful upload information", status=status.HTTP_201_CREATED)
    return Response(status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="get",
    operation_description="Get the stored Run information available in iSkyLIMS for the list of samples",
    manual_parameters=[sample_in_run],
)
@api_view(["GET"])
def fetch_run_information(request):
    if "samples" in request.GET:
        samples = request.GET["samples"]
        # sample_run_info = get_run_info_for_sample(apps_name, samples)
        s_list = samples.strip().split(",")
        s_data = []
        for sample in s_list:
            sample = sample.strip()
            if SamplesInProject.objects.filter(sampleName__iexact=sample).exists():
                s_found_objs = SamplesInProject.objects.filter(
                    sampleName__iexact=sample
                )
                for s_found_obj in s_found_objs:
                    s_data.append(
                        SampleRunInfoSerializers(s_found_obj, many=False).data
                    )
            else:
                s_data.append({"sampleName": sample, "Run data": "Not found"})
        return Response(s_data, status=status.HTTP_200_OK)
    return Response(status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="get", manual_parameters=[sample_information, sample_parameter]
)
@api_view(["GET"])
def fetch_sample_information(request):
    sample_data = {}
    if "sample" in request.GET:
        sample = request.GET["sample"]
        if not Samples.objects.filter(sampleName__iexact=sample).exists():
            return Response(status=status.HTTP_204_NO_CONTENT)
        sample_obj = Samples.objects.filter(sampleName__iexact=sample).last()
        sample_data = SampleSerializer(sample_obj, many=False).data
    else:
        if "parameter" in request.GET:
            param = request.GET["parameter"]
            sample_obj = Samples.objects.all()
            # check if parameter exists
            try:
                eval("sample_obj[0]." + param)
            except AttributeError:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            sample_data = SampleParameterSerializer(
                sample_obj, many=True, context={"parameter": param}
            ).data
        else:
            sample_obj = Samples.objects.prefetch_related("project_values")
            sample_data = SampleSerializer(sample_obj, many=True).data
    return Response(sample_data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    operation_description="Send the request to gen the fields that are required when storing a new sample using the API",
)
@api_view(["GET"])
def sample_fields(request):
    apps_name = __package__.split(".")[0]
    # sample_fields = SampleFieldsSerializer(SampleFields(get_sample_fields(apps_name)))

    sample_fields = get_sample_fields(apps_name)

    if "ERROR" in sample_fields:
        return Response(sample_fields, status=status.HTTP_202_ACCEPTED)
        # return Response(sample_fields.data, status=status.HTTP_204_NO_CONTENT)
    else:
        return Response(sample_fields, status=status.HTTP_200_OK)
    return Response(status=status.HTTP_400_BAD_REQUEST)


"""
@swagger_auto_schema(
    method="get",
    operation_description="Get the samples names grouped by the given parameter",
    manual_parameters=[sample_parameter],
)
@api_view(["GET"])
def fetch_samples_on_parameter(request):
    # Returns the samples that match parameter
    if "sampleParameter" in request.GET:
        data = samples_match_on_parameter(request.GET)
        if data:
            return Response(data, status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(status=status.HTTP_400_BAD_REQUEST)
"""


@swagger_auto_schema(
    method="get",
    operation_description="Use this request to get the field' s names that are required for the sample project",
    manual_parameters=[sample_project_fields],
)
@api_view(["GET"])
def sample_project_fields(request):
    if "project" in request.GET:
        project = request.GET["project"].strip()
        if SampleProjects.objects.filter(sampleProjectName__iexact=project).exists():
            s_project_obj = SampleProjects.objects.filter(
                sampleProjectName__iexact=project
            ).last()
            s_project_field_objs = SampleProjectsFields.objects.filter(
                sampleProjects_id=s_project_obj
            )
            s_project_serializer = SampleProjectFieldSerializer(
                s_project_field_objs, many=True
            )
            return Response(s_project_serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(method="get", manual_parameters=[laboratory])
@api_view(["GET"])
def get_lab_information_contact(request):
    if "laboratory" in request.GET:
        lab_name = request.GET["laboratory"].strip()
        if LabRequest.objects.filter(labName__iexact=lab_name).exists():
            lab_req_obj = LabRequest.objects.filter(labName__iexact=lab_name).last()
            lab_req_serializer = LabRequestSerializer(lab_req_obj, many=False)
            return Response(lab_req_serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="get",
    operation_description="",
    manual_parameters=[
        sample_list,
        sample_state,
        start_date,
        end_date,
        region,
        laboratory,
        sample_project_name,
        sample_project_field,
    ],
)
@api_view(["GET"])
def summarize_data_information(request):
    summarize_data = summarize_samples(request.GET)
    if "ERROR" in summarize_data:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    if len(summarize_data) == 0:
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(summarize_data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    operation_description="",
    manual_parameters=[
        sample_project_name,
        project_fields,
    ],
)
@api_view(["GET"])
def statistic_information(request):
    statistics_data = collect_statistics_information(request.GET)
    if "ERROR" in statistics_data:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    if len(statistics_data) == 0:
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(statistics_data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="put",
    operation_description="Update laboratory contact information",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "lab_name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Name of the Laboratory",
            ),
            "lab_contact_name": openapi.Schema(
                description="Name for laboratory contact",
                type=openapi.TYPE_STRING,
            ),
            "lab_contact_telephone": openapi.Schema(
                description="Phone number of contact",
                type=openapi.TYPE_STRING,
            ),
            "lab_contact_email": openapi.Schema(
                description="Contact email",
                type=openapi.TYPE_STRING,
            ),
        },
    ),
    responses={
        201: "Successful create information",
        204: "Laboratory not defined",
        400: "Bad Request",
        500: "Internal Server Error",
    },
)
@authentication_classes([SessionAuthentication, BasicAuthentication])
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_lab(request):
    if request.method == "PUT":
        data = request.data
        if isinstance(data, QueryDict):
            data = data.dict()
        if "lab_name" in data:
            lab_obj = get_laboratory_instance(data["lab_name"])
            if lab_obj is None:
                return Response(status=status.HTTP_204_NO_CONTENT)
            LabRequestSerializer.update(lab_obj, data)

            return Response(
                "Successful Update information", status=status.HTTP_201_CREATED
            )
    return Response(status=status.HTTP_400_BAD_REQUEST)
