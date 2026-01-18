# hospital/views.py - COMPLETE UPDATED VERSION
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from .models import (
    Appointment, TestRequest, VitalRequest, Vitals, LabResult, MedicalReport, BlogPost
)
import random
from users.models import Profile
from django.db import models
from .serializers import (
    AppointmentSerializer, TestRequestSerializer, VitalRequestSerializer,
    VitalsSerializer, LabResultSerializer, MedicalReportSerializer, AssignmentSerializer, AppointmentAssignmentSerializer,
    StaffProfileSerializer, AppointmentDetailSerializer, 
    BlogPostSerializer, BlogPostCreateSerializer, BlogPostListSerializer
)
from rest_framework.exceptions import PermissionDenied
from .permissions import IsRole
from django.shortcuts import get_object_or_404
from django.db.models import Q
from users.serializers import ProfileSerializer
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Assignment

# --------------- Appointment ---------------
class AppointmentCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsRole]
    allowed_roles = ['PATIENT']
    serializer_class = AppointmentSerializer

    def perform_create(self, serializer):
        profile = self.request.user.profile
        
        # Get available doctors and assign one randomly
        available_doctors = Profile.objects.filter(role='DOCTOR', user__is_active=True)
        assigned_doctor = None
        
        if available_doctors.exists():
            assigned_doctor = random.choice(list(available_doctors))
        
        appointment = serializer.save(patient=profile, doctor=assigned_doctor)
        
        print(f"Appointment created for patient: {profile.user.username}")
        print(f"Assigned doctor: {assigned_doctor}")
        print(f"Appointment data: {serializer.data}")



class AppointmentListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        profile = self.request.user.profile
        if profile.role == 'PATIENT':
            return Appointment.objects.filter(patient=profile).order_by('-booked_at')
        if profile.role == 'DOCTOR':
            # Doctor sees appointments assigned to them
            return Appointment.objects.filter(doctor=profile).order_by('-booked_at')
        # staff/admin/lab/nurse see all for now
        return Appointment.objects.all().order_by('-booked_at')

class AppointmentDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.all()

class AssignmentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssignmentSerializer
    queryset = Assignment.objects.all()
    
    def get_queryset(self):
        profile = self.request.user.profile
        if profile.role == 'ADMIN':
            return Assignment.objects.all()
        elif profile.role == 'DOCTOR':
            return Assignment.objects.filter(
                appointment__doctor=profile
            )
        elif profile.role == 'NURSE':
            return Assignment.objects.filter(staff=profile, role='NURSE')
        elif profile.role == 'LAB':
            return Assignment.objects.filter(staff=profile, role='LAB')
        return Assignment.objects.none()

class AppointmentAssignmentsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssignmentSerializer
    
    def get_queryset(self):
        appointment_id = self.kwargs['appointment_id']
        return Assignment.objects.filter(appointment_id=appointment_id)

class AvailableStaffView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StaffProfileSerializer
    
    def get_queryset(self):
        role = self.request.query_params.get('role')
        if role:
            return Profile.objects.filter(
                role=role,
                user__is_active=True
            )
        return Profile.objects.filter(
            role__in=['DOCTOR', 'NURSE', 'LAB'],
            user__is_active=True
        )

class AssignStaffView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsRole]
    allowed_roles = ['ADMIN', 'DOCTOR']
    
    def post(self, request):
        serializer = AppointmentAssignmentSerializer(data=request.data)
        if serializer.is_valid():
            appointment_id = serializer.validated_data['appointment_id']
            staff_id = serializer.validated_data['staff_id']
            role = serializer.validated_data['role']
            notes = serializer.validated_data.get('notes', '')
            
            try:
                appointment = Appointment.objects.get(id=appointment_id)
                staff = Profile.objects.get(id=staff_id)
                
                # Validate role matches staff role
                if staff.role != role:
                    return Response(
                        {'error': f'Staff member is not a {role}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create or update assignment
                assignment, created = Assignment.objects.update_or_create(
                    appointment=appointment,
                    role=role,
                    defaults={
                        'staff': staff,
                        'assigned_by': request.user.profile,
                        'notes': notes
                    }
                )
                
                # Update appointment with assigned staff based on role
                if role == 'DOCTOR':
                    appointment.doctor = staff
                    appointment.save()
                elif role == 'NURSE':
                    # Create vital request if not exists
                    VitalRequest.objects.get_or_create(
                        appointment=appointment,
                        defaults={
                            'assigned_to': staff,
                            'requested_by': request.user.profile
                        }
                    )
                elif role == 'LAB':
                    # Create test request if not exists
                    TestRequest.objects.get_or_create(
                        appointment=appointment,
                        defaults={
                            'assigned_to': staff,
                            'requested_by': request.user.profile,
                            'tests': 'General tests'
                        }
                    )
                
                return Response({
                    'message': f'Successfully assigned {staff.fullname} as {role}',
                    'assignment': AssignmentSerializer(assignment).data
                })
                
            except Appointment.DoesNotExist:
                return Response(
                    {'error': 'Appointment not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Profile.DoesNotExist:
                return Response(
                    {'error': 'Staff member not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Update AppointmentDetailView to use AppointmentDetailSerializer
class AppointmentDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AppointmentDetailSerializer
    queryset = Appointment.objects.all()

# Add PatientListView
class PatientListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsRole]
    allowed_roles = ['ADMIN', 'DOCTOR']
    serializer_class = StaffProfileSerializer
    
    def get_queryset(self):
        # Get all patients who have appointments
        patient_ids = Appointment.objects.values_list('patient_id', flat=True).distinct()
        return Profile.objects.filter(
            id__in=patient_ids,
            role='PATIENT'
        ).order_by('-user__date_joined')
# --------------- TestRequest (doctor -> lab) ---------------

class TestRequestCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsRole]
    allowed_roles = ['DOCTOR']
    serializer_class = TestRequestSerializer

    def perform_create(self, serializer):
        # Create the test request
        test_request = serializer.save(requested_by=self.request.user.profile)
        
        # Mark appointment as awaiting results
        appt = test_request.appointment
        appt.status = 'AWAITING_RESULTS'
        appt.save()
        
        print(f"Test request created by doctor {self.request.user.profile.fullname}")
        print(f"Assigned to lab scientist: {test_request.assigned_to}")


class TestRequestListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TestRequestSerializer

    def get_queryset(self):
        profile = self.request.user.profile
        if profile.role == 'LAB':
            # lab scientists see requests assigned to them or all pending
            return TestRequest.objects.filter(models.Q(assigned_to=profile) | models.Q(status='PENDING')).order_by('-created_at')
        if profile.role == 'DOCTOR':
            return TestRequest.objects.filter(requested_by=profile).order_by('-created_at')
        return TestRequest.objects.all().order_by('-created_at')

# --------------- VitalRequest (doctor -> nurse) ---------------

class VitalRequestCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsRole]
    allowed_roles = ['DOCTOR']
    serializer_class = VitalRequestSerializer

    def perform_create(self, serializer):
        # Create the vital request
        vital_request = serializer.save(requested_by=self.request.user.profile)
        
        # Mark appointment as in review
        appt = vital_request.appointment
        appt.status = 'IN_REVIEW'
        appt.save()
        
        print(f"Vital request created by doctor {self.request.user.profile.fullname}")
        print(f"Assigned to nurse: {vital_request.assigned_to}")


class VitalRequestListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = VitalRequestSerializer

    def get_queryset(self):
        profile = self.request.user.profile
        if profile.role == 'NURSE':
            return VitalRequest.objects.filter(models.Q(assigned_to=profile) | models.Q(status='PENDING')).order_by('-created_at')
        if profile.role == 'DOCTOR':
            return VitalRequest.objects.filter(requested_by=profile).order_by('-created_at')
        return VitalRequest.objects.all().order_by('-created_at')


# --------------- Nurse fills Vitals ---------------
class VitalsCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsRole]
    allowed_roles = ['NURSE']
    serializer_class = VitalsSerializer

    def perform_create(self, serializer):
        vitals = serializer.save(nurse=self.request.user.profile)
        vital_request = vitals.vital_request
        
        # Mark vital request as done
        vital_request.status = 'DONE'
        vital_request.save()
        
        appointment = vital_request.appointment
        print(f"Vitals recorded for {appointment.name}")
        print(f"BP: {vitals.blood_pressure}, Pulse: {vitals.pulse_rate}")


# --------------- Lab scientist fills LabResult ---------------
class LabResultCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsRole]
    allowed_roles = ['LAB']
    serializer_class = LabResultSerializer

    def perform_create(self, serializer):
        lab_result = serializer.save(lab_scientist=self.request.user.profile)
        test_request = lab_result.test_request
        
        # Update appointment status when results are submitted
        appointment = test_request.appointment
        
        print(f"Lab result submitted for {appointment.name}")
        print(f"Test: {lab_result.test_name}, Result: {lab_result.result}")
        
        # Check if all requested tests have results
        requested_tests = [test.strip() for test in test_request.tests.split(',')]
        completed_tests = test_request.lab_results.values_list('test_name', flat=True)
        
        # If all tests have results, mark test request as done
        if set(requested_tests).issubset(set(completed_tests)):
            test_request.status = 'DONE'
            test_request.save()
            print(f"All tests completed for {appointment.name}")

# --------------- Doctor creates Medical Report ---------------
class MedicalReportCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsRole]
    allowed_roles = ['DOCTOR']
    serializer_class = MedicalReportSerializer

    def perform_create(self, serializer):
        serializer.save(doctor=self.request.user.profile)
        # Appointment status updated in MedicalReport.save()


class StaffListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProfileSerializer

    def get_queryset(self):
        # Return all staff members (doctors, nurses, lab scientists)
        return Profile.objects.filter(
            Q(role='DOCTOR') | Q(role='NURSE') | Q(role='LAB')
        ).filter(user__is_active=True)
    
# In hospital/views.py - Update AvailableStaffView
class AvailableStaffView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StaffProfileSerializer
    
    def get_queryset(self):
        role = self.request.query_params.get('role')
        
        if role:
            # Validate the role
            valid_roles = ['DOCTOR', 'NURSE', 'LAB']
            if role.upper() not in valid_roles:
                return Profile.objects.none()
            
            # Filter by specific role
            return Profile.objects.filter(
                role=role.upper(),
                user__is_active=True
            )
        
        # If no role specified, return all staff (DOCTOR, NURSE, LAB)
        return Profile.objects.filter(
            role__in=['DOCTOR', 'NURSE', 'LAB'],
            user__is_active=True
        )

# ==================== UPDATED BLOG VIEWS WITH PROPER SERIALIZERS ====================

class BlogPostListCreateView(generics.ListCreateAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        # For GET requests, show published posts to everyone
        if self.request.method == "GET":
            return BlogPost.objects.filter(published=True)
        # For POST requests, check authentication
        return BlogPost.objects.all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BlogPostCreateSerializer
        return BlogPostListSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsRole()]
        return [permissions.AllowAny()]  # Allow anyone to view

    def perform_create(self, serializer):
        profile = self.request.user.profile
        if profile.role != "ADMIN":
            raise PermissionDenied("Only admins can create blog posts.")
        
        try:
            print(f"📝 Creating blog post with data: {self.request.data}")
            print(f"📁 Files received: {self.request.FILES}")

            # Check if images are present
            for field in ['featured_image', 'image_1', 'image_2']:
                if field in self.request.FILES:
                    print(f"✅ {field} file found: {self.request.FILES[field].name} ({self.request.FILES[field].size} bytes)")
                else:
                    print(f"⚠️  {field} not found in files")
            
            # Save the blog post
            blog_post = serializer.save(author=profile)
            
            print(f"✅ Blog post created: {blog_post.id}")
            print(f"📸 Images saved to model:")
            print(f"  - featured_image: {blog_post.featured_image}")
            print(f"  - image_1: {blog_post.image_1}")
            print(f"  - image_2: {blog_post.image_2}")

            # The signal handler will automatically upload images to S3
            print(f"📤 Signal handler will upload images to S3 automatically")
            
            return blog_post
            
        except Exception as e:
            print(f"❌ Error creating blog post: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

class BlogPostRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = BlogPost.objects.all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.request.method == "GET":
            return BlogPostSerializer
        return BlogPostCreateSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsRole()]

    def perform_update(self, serializer):
        profile = self.request.user.profile
        if profile.role != "ADMIN":
            raise PermissionDenied("Only admins can update blog posts.")
        serializer.save()

    def perform_destroy(self, instance):
        profile = self.request.user.profile
        if profile.role != "ADMIN":
            raise PermissionDenied("Only admins can delete blog posts.")
        instance.delete()

class BlogPostSearchView(generics.ListAPIView):
    serializer_class = BlogPostListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = BlogPost.objects.filter(published=True)
        search_query = self.request.query_params.get('q', None)
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(content__icontains=search_query)
            )
        return queryset.order_by('-created_at')

class AdminBlogPostListView(generics.ListAPIView):
    serializer_class = BlogPostListSerializer
    permission_classes = [permissions.IsAuthenticated, IsRole]
    allowed_roles = ['ADMIN']
    
    def get_queryset(self):
        return BlogPost.objects.all().order_by('-created_at')

class BlogPostLatestView(generics.ListAPIView):
    serializer_class = BlogPostListSerializer  # Changed from BlogPostSerializer to BlogPostListSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        limit = self.request.query_params.get('limit', 6)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 6
        
        user = self.request.user
        
        # For authenticated admin users, show all posts
        if user.is_authenticated and hasattr(user, "profile") and user.profile.role == "ADMIN":
            queryset = BlogPost.objects.all()
        else:
            # For public users, only show published posts
            queryset = BlogPost.objects.filter(published=True)
        
        # Order by date
        if queryset.filter(published_date__isnull=False).exists():
            queryset = queryset.order_by('-published_date')
        else:
            queryset = queryset.order_by('-created_at')
            
        return queryset[:limit]

class BlogPostByAuthorView(generics.ListAPIView):
    serializer_class = BlogPostListSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        author_id = self.kwargs['author_id']
        return BlogPost.objects.filter(
            author_id=author_id, 
            published=True
        ).order_by('-published_date', '-created_at')

class BlogStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsRole]
    allowed_roles = ['ADMIN']
    
    def get(self, request):
        total_posts = BlogPost.objects.count()
        published_posts = BlogPost.objects.filter(published=True).count()
        draft_posts = total_posts - published_posts
        posts_with_toc = BlogPost.objects.filter(enable_toc=True).count()
        
        return Response({
            'total_posts': total_posts,
            'published_posts': published_posts,
            'draft_posts': draft_posts,
            'posts_with_toc': posts_with_toc,
            'toc_usage_rate': (posts_with_toc / total_posts * 100) if total_posts > 0 else 0
        })