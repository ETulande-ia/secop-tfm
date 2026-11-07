import { Component, signal } from '@angular/core';
import { Chat } from '../chat/chat';
import { Header } from '../layout/header/header';
import { Footer } from '../layout/footer/footer';
import { MapaTerritorialComponent } from '../features/mapa-territorial/mapa-territorial';

@Component({
  selector: 'app-transparencia-ia-assistant',
  standalone: true,
  imports: [
    Chat,
    Header,
    Footer,
    MapaTerritorialComponent
  ],
  templateUrl: './transparencia-ia-assistant.html',
  styleUrl: './transparencia-ia-assistant.scss',
})
export class TransparenciaIaAssistant {
  vista = signal<'chat' | 'mapa'>('chat');
}
