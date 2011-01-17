import copy
import datetime

from django.contrib.contenttypes.models import ContentType

from workflows.models import State
from workflows.utils import (get_workflow_for_object, set_workflow_for_object,
                             get_state)

from ietf.ietfworkflows.models import (WGWorkflow, AnnotationTagObjectRelation,
                                       AnnotationTag, ObjectAnnotationTagHistoryEntry)


WAITING_WRITEUP = 'WG Consensus: Waiting for Write-Up'
FOLLOWUP_TAG = 'Doc Shepherd Follow-up Underway'


def get_default_workflow_for_wg():
    try:
        workflow = WGWorkflow.objects.get(name='Default WG Workflow')
        return workflow
    except WGWorkflow.DoesNotExist:
        return None
    
def clone_transition(transition):
    new = copy.copy(transition)
    new.pk = None
    new.save()

    # Reference original initial states
    for state in transition.states.all():
        new.states.add(state)
    return new

def clone_workflow(workflow, name):
    new = WGWorkflow.objects.create(name=name, initial_state=workflow.initial_state)

    # Reference default states
    for state in workflow.states.all():
        new.selected_states.add(state)

    # Reference default annotation tags
    for tag in workflow.annotation_tags.all():
        new.selected_tags.add(tag)

    # Reference cloned transitions
    for transition in workflow.transitions.all():
        new.transitions.add(clone_transition(transition))
    return new

def get_workflow_for_wg(wg):
    workflow = get_workflow_for_object(wg)
    try:
        workflow = workflow and workflow.wgworkflow
    except WGWorkflow.DoesNotExist:
        workflow = None
    if not workflow:
        workflow = get_default_workflow_for_wg()
        if not workflow:
            return None
        workflow = clone_workflow(workflow, name='%s workflow' % wg)
        set_workflow_for_object(wg, workflow)
    return workflow

def get_workflow_for_draft(draft):
    workflow = get_workflow_for_object(draft)
    try:
        workflow = workflow and workflow.wgworkflow
    except WGWorkflow.DoesNotExist:
        workflow = None
    if not workflow:
        workflow = get_workflow_for_wg(draft.group.ietfwg)
        set_workflow_for_object(draft, workflow)
    return workflow


def get_annotation_tags_for_draft(draft):
    ctype = ContentType.objects.get_for_model(draft)
    tags = AnnotationTagObjectRelation.objects.filter(content_type=ctype, content_id=draft.pk)
    return tags


def get_state_for_draft(draft):
    return get_state(draft)


def get_state_by_name(state_name):
    try:
        return State.objects.get(name=state_name)
    except State.DoesNotExist:
        return None


def get_annotation_tag_by_name(tag_name):
    try:
        return AnnotationTag.objects.get(name=tag_name)
    except AnnotationTag.DoesNotExist:
        return None

def set_tag_by_name(obj, tag_name):
    ctype = ContentType.objects.get_for_model(obj)
    try:
        tag = AnnotationTag.objects.get(name=tag_name)
        (relation, created) = AnnotationTagObjectRelation.objects.get_or_create(
            content_type=ctype,
            content_id=obj.pk,
            annotation_tag=tag)
    except AnnotationTag.DoesNotExist:
        return None
    return relation


def reset_tag_by_name(obj, tag_name):
    ctype = ContentType.objects.get_for_model(obj)
    try:
        tag = AnnotationTag.objects.get(name=tag_name)
        tag_relation = AnnotationTagObjectRelation.objects.get(
            content_type=ctype,
            content_id=obj.pk,
            annotation_tag=tag)
        tag_relation.delete()
        return True
    except AnnotationTagObjectRelation.DoesNotExist:
        return False
    except AnnotationTag.DoesNotExist:
        return False


def update_tags(obj, comment, set_tags=[], reset_tags=[]):
    ctype = ContentType.objects.get_for_model(obj)
    setted = []
    resetted = []
    for name in set_tags:
        if set_tag_by_name(obj, name):
            setted.append(name)
    for name in reset_tags:
        if reset_tag_by_name(obj, name):
            resetted.append(name)
    ObjectAnnotationTagHistoryEntry.objects.create(
        content_type=ctype,
        content_id=obj.pk,
        setted = ','.join(setted),
        unsetted = ','.join(resetted),
        change_date = datetime.datetime.now(),
        comment = comment)
