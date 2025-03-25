<% 
    import re
    def render_item(item):
        return re.sub(r'\s+', ' ', str(item)).strip()
%>
