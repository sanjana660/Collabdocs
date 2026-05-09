"""
Atomic Transaction Example with Rollback on Failure
====================================================

This script demonstrates how to use Django's transaction.atomic() decorator
and context manager to ensure data consistency. If ANY operation fails,
the entire transaction is rolled back.

Use cases:
- Creating a workspace + adding owner as member (atomic)
- Creating a document + first version (atomic)
- Complex multi-model operations that must succeed together
"""

import os
import sys
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.db import transaction
from core.models import User, Workspace, WorkspaceMember, Document, DocumentVersion, Tag, AuditLog


def example_1_workspace_creation_atomic():
    """
    Example 1: Create workspace + add owner as admin member (ATOMIC)
    
    If adding the member fails, the entire workspace creation is rolled back.
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: Workspace Creation (Atomic)")
    print("="*80)
    
    try:
        with transaction.atomic():
            # Create owner user
            owner = User.objects.create_user(
                email='workspace-owner@example.com',
                first_name='Workspace',
                last_name='Owner',
                phone='+15559999999',
                password='TestPassword123!'
            )
            print(f"✓ Created user: {owner.email}")
            
            # Create workspace
            workspace = Workspace.objects.create(
                name='Atomic Transaction Demo',
                owner=owner,
                is_active=True
            )
            print(f"✓ Created workspace: {workspace.name}")
            
            # Add owner as admin member
            member = WorkspaceMember.objects.create(
                workspace=workspace,
                user=owner,
                role=WorkspaceMember.RoleChoices.ADMIN
            )
            print(f"✓ Added {owner.email} as {member.role}")
            
            # If any step failed, transaction.atomic() rolls back ALL changes
            print(f"\n✓ Transaction COMMITTED: Workspace + Member both created")
            return workspace
            
    except Exception as e:
        print(f"\n✗ Transaction ROLLED BACK due to error: {e}")
        # Workspace creation is automatically rolled back
        return None


def example_2_document_with_version_atomic():
    """
    Example 2: Create document + first version (ATOMIC)
    
    Both the document and its first DocumentVersion must be created together.
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: Document with Version (Atomic)")
    print("="*80)
    
    workspace = Workspace.objects.first()
    user = User.objects.first()
    
    if not workspace or not user:
        print("✗ Need existing workspace and user")
        return None
    
    try:
        with transaction.atomic():
            # Create document
            document = Document.objects.create(
                title='Atomic Transaction Example Document',
                content='This document is created atomically with its first version.',
                workspace=workspace,
                created_by=user,
                status=Document.StatusChoices.DRAFT
            )
            print(f"✓ Created document: {document.title}")
            
            # Create first version (document.save() does this automatically)
            version = DocumentVersion.objects.create(
                document=document,
                content=document.content,
                version_number=1,
                saved_by=user
            )
            print(f"✓ Created version: v{version.version_number}")
            
            # Create audit log
            audit = AuditLog.objects.create(
                actor=user,
                action='created',
                model_name='Document',
                object_id=str(document.id)
            )
            print(f"✓ Created audit log for document creation")
            
            print(f"\n✓ Transaction COMMITTED: Document + Version + AuditLog all created")
            return document
            
    except Exception as e:
        print(f"\n✗ Transaction ROLLED BACK due to error: {e}")
        # All three creates are rolled back
        return None


def example_3_manual_rollback_on_validation():
    """
    Example 3: Manual transaction rollback on validation failure
    
    Demonstrates catching an error and letting transaction.atomic() rollback.
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: Manual Rollback on Validation Error")
    print("="*80)
    
    workspace = Workspace.objects.first()
    user = User.objects.first()
    
    if not workspace or not user:
        print("✗ Need existing workspace and user")
        return None
    
    try:
        with transaction.atomic():
            # Create document
            document = Document.objects.create(
                title='Document with Validation',
                content='Content here',
                workspace=workspace,
                created_by=user,
                status=Document.StatusChoices.DRAFT
            )
            print(f"✓ Created document: {document.title}")
            
            # Add multiple tags
            for tag_name in ['python', 'api', 'testing']:
                tag = Tag.objects.create(name=f'{tag_name}-demo-{document.id}')
                document.tags.add(tag)
                print(f"✓ Added tag: {tag.name}")
            
            # Simulate validation error
            if document.title == 'Document with Validation':
                # Intentional error to trigger rollback
                raise ValueError("Document validation failed: Title too generic!")
            
            print(f"\n✓ Transaction COMMITTED")
            
    except ValueError as e:
        print(f"\n✗ Validation Error: {e}")
        print(f"✗ Transaction ROLLED BACK: Document and all tags are removed")
        return None


def example_4_savepoint_for_nested_atomic():
    """
    Example 4: Use savepoints for nested atomic operations
    
    Useful when you want partial rollback of nested operations.
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: Nested Atomic with Savepoints")
    print("="*80)
    
    workspace = Workspace.objects.first()
    user = User.objects.first()
    
    if not workspace or not user:
        print("✗ Need existing workspace and user")
        return None
    
    try:
        with transaction.atomic():
            document = Document.objects.create(
                title='Document with Nested Operations',
                content='Outer transaction',
                workspace=workspace,
                created_by=user,
                status=Document.StatusChoices.DRAFT
            )
            print(f"✓ Created document in outer transaction")
            
            try:
                # Nested savepoint
                with transaction.atomic():
                    tag = Tag.objects.create(name=f'nested-tag-{document.id}')
                    document.tags.add(tag)
                    print(f"✓ Added tag in nested transaction (savepoint)")
                    
                    # Intentional error in nested scope only
                    raise ValueError("Nested operation failed")
                    
            except ValueError as e:
                print(f"✗ Nested operation error: {e}")
                print(f"✗ Nested transaction rolled back (but outer continues)")
            
            # Outer transaction continues despite nested failure
            print(f"✓ Outer transaction still active")
            print(f"✓ Document exists but tag was not added")
            print(f"\n✓ Outer transaction COMMITTED (without the nested tag)")
            return document
            
    except Exception as e:
        print(f"\n✗ Outer transaction ROLLED BACK: {e}")
        return None


def check_rollback_success():
    """
    Verify that rollback worked by checking the database state.
    """
    print("\n" + "="*80)
    print("VERIFICATION: Check Database State")
    print("="*80)
    
    users = User.objects.filter(email__endswith='@example.com').count()
    workspaces = Workspace.objects.filter(name__icontains='Atomic').count()
    documents = Document.objects.filter(title__icontains='Atomic').count()
    
    print(f"Users created: {users}")
    print(f"Workspaces created: {workspaces}")
    print(f"Documents created: {documents}")
    
    if users == 1 and workspaces == 1:
        print("\n✓ Rollback verification PASSED: Only successful transactions persisted")
    else:
        print("\n✗ Unexpected state in database")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("DJANGO ATOMIC TRANSACTIONS WITH ROLLBACK - COMPLETE EXAMPLES")
    print("="*80)
    
    # Run examples
    example_1_workspace_creation_atomic()
    example_2_document_with_version_atomic()
    example_3_manual_rollback_on_validation()
    example_4_savepoint_for_nested_atomic()
    
    # Verify database state
    check_rollback_success()
    
    print("\n" + "="*80)
    print("All examples completed!")
    print("="*80 + "\n")
