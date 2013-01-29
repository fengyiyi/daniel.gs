from flask import g, request, render_template, render_template_string

def _add_more_context(**context):
	# provide more context entries
	more_context = {
		'request_path': request.path,
		'args': request.args.to_dict(),
	}
	# but, caller's context entries can override them
	more_context.update(context)
	return more_context

def render(template_name, **context):
	return render_template(template_name, **_add_more_context(**context))

def render_string(source, **context):
	return render_template_string(source, **_add_more_context(**context))