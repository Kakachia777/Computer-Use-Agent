from typing import Dict, List
import inspect
import os
import yaml
from jinja2 import Environment, FileSystemLoader

class DocGenerator:
    """Generates comprehensive documentation for the project."""
    
    def __init__(self, output_dir: str = "generated_docs"):
        self.output_dir = output_dir
        self.env = Environment(loader=FileSystemLoader('doc_templates'))
        
    def generate_all(self):
        """Generate all documentation."""
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Generate different types of documentation
        self.generate_api_docs()
        self.generate_user_guide()
        self.generate_developer_guide()
        self.generate_metrics_docs()
        
    def generate_api_docs(self):
        """Generate API documentation from docstrings."""
        api_docs = []
        
        for module in self._get_modules():
            module_docs = self._process_module(module)
            api_docs.append(module_docs)
            
        template = self.env.get_template('api_template.md')
        output = template.render(modules=api_docs)
        
        with open(f"{self.output_dir}/api_documentation.md", 'w') as f:
            f.write(output) 