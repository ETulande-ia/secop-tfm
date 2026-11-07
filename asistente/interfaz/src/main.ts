import { createApplication } from '@angular/platform-browser';
import { createCustomElement } from '@angular/elements';
import { TransparenciaIaAssistant } from './app/transparencia-ia-assistant/transparencia-ia-assistant';
import { provideHttpClient } from '@angular/common/http';
import { provideMarkdown } from 'ngx-markdown';




(async () => {
  const app = await createApplication({
    providers: [
       provideHttpClient(),
         provideMarkdown()
    ]
  });

  const transparenciaIaAssistantElement = createCustomElement(TransparenciaIaAssistant, {
    injector: app.injector
  });

  customElements.define('app-transparencia-ia-assistant', transparenciaIaAssistantElement);
})();
