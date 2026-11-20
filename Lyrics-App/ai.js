const aiState={configured:false,providers:[],provider:'openai',conversationId:null,conversations:[],busy:false,welcomeChecked:false,listening:false,recognition:null,voiceOutput:false,activeSpeechButton:null};
const aiMessages=$('#aiMessages');
const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
const supportsSpeechOutput=Boolean(window.speechSynthesis&&window.SpeechSynthesisUtterance);
try{
	aiState.voiceOutput=supportsSpeechOutput&&localStorage.getItem('lyrics.ai.voice-output.v1')==='true';
}catch(error){
	console.error('No se pudo leer la preferencia de voz de la IA:',error);
}

function showAiWelcomeOnce(){
	if(aiState.welcomeChecked)return;
	aiState.welcomeChecked=true;
	try{
		if(localStorage.getItem('lyrics.ai.welcome.v1'))return;
	}catch(error){
		console.error('No se pudo leer la preferencia de bienvenida de la IA:',error);
	}
	$('#aiWelcome').hidden=false;
	window.setTimeout(()=>$('#aiWelcomeEnter').focus(),0);
}
function playWelcomeArpeggio(){
	const AudioContext=window.AudioContext||window.webkitAudioContext;
	if(!AudioContext){
		setAiStatus('Este navegador no permite reproducir el arpegio; puedes continuar.',true);
		return;
	}
	try{
		const context=new AudioContext(),notes=[261.63,329.63,392,523.25],start=context.currentTime+.04;
		context.resume().catch(error=>{
			console.error('No se pudo activar el audio de bienvenida:',error);
			setAiStatus('No se pudo reproducir el arpegio; puedes continuar.',true);
		});
		notes.forEach((frequency,index)=>{
			const time=start+index*.17,oscillator=context.createOscillator(),gain=context.createGain();
			oscillator.type='sine';
			oscillator.frequency.setValueAtTime(frequency,time);
			gain.gain.setValueAtTime(.0001,time);
			gain.gain.exponentialRampToValueAtTime(.075,time+.025);
			gain.gain.exponentialRampToValueAtTime(.0001,time+.22);
			oscillator.connect(gain);gain.connect(context.destination);
			oscillator.start(time);oscillator.stop(time+.24);
		});
		window.setTimeout(()=>context.close().catch(error=>console.error('No se pudo cerrar el contexto de audio:',error)),1200);
	}catch(error){
		console.error('No se pudo reproducir el arpegio de bienvenida:',error);
		setAiStatus('No se pudo reproducir el arpegio; puedes continuar.',true);
	}
}
$('#aiWelcomeEnter').onclick=()=>{
	const overlay=$('#aiWelcome'),button=$('#aiWelcomeEnter');
	if($('#aiWelcomeSound').checked)playWelcomeArpeggio();
	button.disabled=true;
	overlay.dataset.closing='true';
	window.setTimeout(()=>{
		overlay.hidden=true;
		button.disabled=false;
		try{
			localStorage.setItem('lyrics.ai.welcome.v1','seen');
		}catch(error){
			console.error('No se pudo guardar la preferencia de bienvenida de la IA:',error);
			toast('La bienvenida podría volver a aparecer en otra sesión.');
		}
		$('#aiMessageInput').focus();
	},800);
};

function setAiFaceState(state,label){
	const face=$('#aiFace');
	face.dataset.state=state;
	face.setAttribute('aria-label',label);
}
function setAiSceneCaption(message){
	$('#aiSceneCaption').textContent=message;
}
function setAiStatus(message,isError=false){
	const status=$('#aiConnectionStatus');
	status.textContent=message;
	status.classList.toggle('is-error',isError);
}
function configureAiProviders(config){
	aiState.providers=Array.isArray(config.providers)?config.providers.filter(provider=>
		provider&&['openai','gemini','local'].includes(provider.id)&&provider.configured
	):[];
	let preferredProvider='';
	try{
		preferredProvider=localStorage.getItem('lyrics.ai.provider.v1')||'';
	}catch(error){
		console.error('No se pudo leer el proveedor de IA guardado:',error);
	}
	const selected=aiState.providers.find(provider=>provider.id===preferredProvider)
		||aiState.providers.find(provider=>provider.id===config.default_provider)
		||aiState.providers[0];
	aiState.provider=selected?selected.id:(config.default_provider||'openai');
	const select=$('#aiProviderSelect');
	select.replaceChildren();
	if(!aiState.providers.length){
		const option=document.createElement('option');
		option.value='';
		option.textContent='Sin proveedor';
		select.append(option);
		select.disabled=true;
		select.title='Configura OPENAI_API_KEY o GEMINI_API_KEY en el archivo .env del servidor.';
		return;
	}
	aiState.providers.forEach(provider=>{
		const option=document.createElement('option');
		option.value=provider.id;
		option.textContent=provider.name;
		select.append(option);
	});
	select.value=aiState.provider;
	select.disabled=aiState.busy||aiState.providers.length<2;
	const externalProviders=aiState.providers.filter(provider=>provider.id!=='local');
	const missingProvider=externalProviders.length===1
		?(externalProviders[0].id==='openai'?'Gemini':'OpenAI')
		:'';
	const missingKey=missingProvider==='Gemini'?'GEMINI_API_KEY':'OPENAI_API_KEY';
	select.title=missingProvider?`Para alternar, configura ${missingKey} en el archivo .env del servidor.`:'';
}
/* Personalización de la IA: nivel musical guardado en el servidor y sugerencias según el rol. */
const AI_LEVEL_LABELS={principiante:'Principiante',intermedio:'Intermedio',avanzado:'Avanzado'};
const AI_SUGGESTIONS_BY_ROLE={
	docente:[
		['Crear evaluación','Crea un borrador de evaluación de teoría musical, con preguntas variadas y clave de respuestas separada. Pregúntame el nivel del grupo si lo necesitas.'],
		['Diseñar dictado','Propón un dictado rítmico sencillo en 3/4 y explica cómo trabajarlo en clase.'],
		['Plan de clase','Ayúdame a planear una clase de 45 minutos sobre intervalos musicales, con objetivo, actividades y cierre.']
	],
	compositor:[
		['Idea de melodía','Dame una idea de melodía en tonalidad menor con una progresión de acordes y explica por qué funciona.'],
		['Desarrollar motivo','Tengo un motivo de cuatro notas. Explícame técnicas para desarrollarlo en una sección completa.'],
		['Consultar armonía','Explícame cómo elegir acordes para armonizar una melodía de ocho compases.']
	]
};
AI_SUGGESTIONS_BY_ROLE.mixto=[...AI_SUGGESTIONS_BY_ROLE.docente.slice(0,1),...AI_SUGGESTIONS_BY_ROLE.compositor.slice(0,2)];
AI_SUGGESTIONS_BY_ROLE.administrador=AI_SUGGESTIONS_BY_ROLE.mixto;
function renderAiSuggestions(role){
	const items=AI_SUGGESTIONS_BY_ROLE[role];
	if(!items)return; // sin rol conocido se conservan las sugerencias del HTML
	const container=$('#aiSuggestions');
	container.replaceChildren(...items.map(([label,prompt])=>{
		const button=document.createElement('button');
		button.type='button';
		button.dataset.aiPrompt=prompt;
		button.textContent=label;
		return button;
	}));
}
function configureAiLevel(config){
	const select=$('#aiLevelSelect');
	const levels=Array.isArray(config.levels)&&config.levels.length?config.levels:Object.keys(AI_LEVEL_LABELS);
	select.replaceChildren(...levels.map(level=>{
		const option=document.createElement('option');
		option.value=level;
		option.textContent=AI_LEVEL_LABELS[level]||level;
		return option;
	}));
	select.value=levels.includes(config.level)?config.level:'intermedio';
	select.dataset.saved=select.value;
	select.disabled=false;
}
function selectedAiProvider(){
	return aiState.providers.find(provider=>provider.id===aiState.provider)||null;
}
function updateAiProviderStatus(){
	const provider=selectedAiProvider();
	if(provider?.id==='local'){
		setAiStatus('Asistente local listo · respuestas musicales guiadas, sin IA generativa.');
		return;
	}
	if(provider){
		const switchHint=aiState.providers.length===1
			?` · Configura ${provider.id==='openai'?'GEMINI_API_KEY':'OPENAI_API_KEY'} para alternar`
			:'';
		setAiStatus(`Configurado · ${provider.name} · ${provider.model} · respaldo automático${switchHint}`);
	}
}
function updateAiVoiceControls(){
	const button=$('#aiVoiceOutput');
	button.disabled=!supportsSpeechOutput;
	button.classList.toggle('is-active',aiState.voiceOutput);
	button.setAttribute('aria-pressed',String(aiState.voiceOutput));
	button.setAttribute('aria-label',aiState.voiceOutput?'Desactivar lectura automática de respuestas':'Activar lectura automática de respuestas');
	button.title=supportsSpeechOutput
		?(aiState.voiceOutput?'Desactivar lectura automática':'Leer las respuestas en voz alta')
		:'La lectura en voz alta no está disponible en este navegador';
	button.querySelector('span:last-child').textContent=supportsSpeechOutput
		?(aiState.voiceOutput?'Voz activada':'Voz apagada')
		:'Voz no disponible';
	const mic=$('#aiMicButton');
	mic.disabled=!SpeechRecognition||!aiState.configured||aiState.busy;
	mic.classList.toggle('is-listening',aiState.listening);
	mic.setAttribute('aria-pressed',String(aiState.listening));
	mic.setAttribute('aria-label',aiState.listening?'Detener dictado':'Hablar con el asistente');
	mic.title=!SpeechRecognition
		?'El dictado por voz no está disponible en este navegador'
		:aiState.listening?'Detener dictado':'Dictar mensaje';
}
function setVoiceOutput(enabled,persist=true){
	aiState.voiceOutput=Boolean(enabled)&&supportsSpeechOutput;
	if(!aiState.voiceOutput)stopAiSpeech();
	updateAiVoiceControls();
	if(persist){
		try{
			localStorage.setItem('lyrics.ai.voice-output.v1',String(aiState.voiceOutput));
		}catch(error){
			console.error('No se pudo guardar la preferencia de lectura por voz:',error);
			toast('No se pudo guardar la preferencia de voz.');
		}
	}
	if(!supportsSpeechOutput)setAiStatus('Este navegador no dispone de lectura de voz.',true);
	else setAiStatus(aiState.voiceOutput?'Leeré las respuestas en voz alta.':'La lectura automática está desactivada.');
}
function stopAiSpeech(){
	if(!supportsSpeechOutput)return;
	const wasSpeaking=window.speechSynthesis.speaking||window.speechSynthesis.pending||Boolean(aiState.activeSpeechButton);
	window.speechSynthesis.cancel();
	if(aiState.activeSpeechButton){
		aiState.activeSpeechButton.textContent='◖ Leer';
		aiState.activeSpeechButton.setAttribute('aria-label','Leer respuesta en voz alta');
		aiState.activeSpeechButton=null;
	}
	if($('#aiFace').dataset.state==='speaking')setAiFaceState('idle','Asistente musical en espera');
	if(wasSpeaking){
		setAiSceneCaption('Puedes escribir o dictar cuando quieras.');
		setAiStatus('Lectura de voz detenida.');
	}
}
function speakAiText(content,button=null){
	if(!supportsSpeechOutput){
		setAiStatus('Este navegador no dispone de lectura de voz.',true);
		return;
	}
	if(window.speechSynthesis.speaking||window.speechSynthesis.pending){
		const wasActiveButton=aiState.activeSpeechButton;
		stopAiSpeech();
		if(wasActiveButton===button)return;
	}
	const text=content
		.replace(/```[\s\S]*?```/g,' ')
		.replace(/!\[([^\]]*)\]\([^)]+\)/g,'$1')
		.replace(/\[([^\]]+)\]\([^)]+\)/g,'$1')
		.replace(/^#{1,6}\s*/gm,'')
		.replace(/[*_`~>#]/g,'')
		.trim();
	if(!text)return;
	const utterance=new SpeechSynthesisUtterance(text);
	utterance.lang='es-CO';
	const voices=window.speechSynthesis.getVoices();
	utterance.voice=voices.find(voice=>voice.lang.toLowerCase()==='es-co')
		||voices.find(voice=>voice.lang.toLowerCase().startsWith('es'))
		||null;
	utterance.onstart=()=>{
		setAiFaceState('speaking','El asistente está hablando');
		setAiSceneCaption('Estoy aquí, hablando contigo.');
		setAiStatus('Reproduciendo respuesta de voz…');
		if(button){
			aiState.activeSpeechButton=button;
			button.textContent='■ Detener';
			button.setAttribute('aria-label','Detener lectura de la respuesta');
		}
	};
	utterance.onend=()=>{
		if(button&&aiState.activeSpeechButton===button){
			button.textContent='◖ Leer';
			button.setAttribute('aria-label','Leer respuesta en voz alta');
			aiState.activeSpeechButton=null;
		}
		if($('#aiFace').dataset.state==='speaking')setAiFaceState('idle','Asistente musical en espera');
		setAiSceneCaption('¿Qué te gustaría crear ahora?');
		setAiStatus('Respuesta lista.');
	};
	utterance.onerror=event=>{
		if(button){
			button.textContent='◖ Leer';
			button.setAttribute('aria-label','Leer respuesta en voz alta');
			aiState.activeSpeechButton=null;
		}
		if(event.error!=='canceled'&&event.error!=='interrupted'){
			console.error('No se pudo reproducir la respuesta de voz:',event.error);
			setAiStatus('No se pudo reproducir la respuesta de voz en este navegador.',true);
		}
		if($('#aiFace').dataset.state==='speaking')setAiFaceState('idle','Asistente musical en espera');
		setAiSceneCaption('Puedes escribir o dictar cuando quieras.');
	};
	window.speechSynthesis.speak(utterance);
}
function stopAiListening(){
	if(aiState.recognition){
		try{
			aiState.recognition.stop();
		}catch(error){
			console.error('No se pudo detener el dictado:',error);
		}
	}
}
function startAiListening(){
	if(!SpeechRecognition){
		setAiStatus('El dictado por voz requiere un navegador compatible, como Chrome o Edge.',true);
		return;
	}
	if(!aiState.configured){
		setAiStatus('Configura primero el servicio de IA para enviar el mensaje dictado.',true);
		return;
	}
	if(aiState.listening){
		stopAiListening();
		return;
	}
	stopAiSpeech();
	const input=$('#aiMessageInput'),baseText=input.value.trim();
	const recognition=new SpeechRecognition();
	aiState.recognition=recognition;
	let recognitionError=false;
	recognition.lang=(navigator.language&&navigator.language.toLowerCase().startsWith('es'))
		?navigator.language:'es-CO';
	recognition.continuous=false;
	recognition.interimResults=true;
	recognition.maxAlternatives=1;
	recognition.onstart=()=>{
		aiState.listening=true;
		updateAiVoiceControls();
		setAiFaceState('listening','El asistente está escuchando');
		setAiSceneCaption('Te escucho…');
		setAiStatus('Escuchando. Habla ahora y vuelve a tocar el micrófono para terminar.');
		$('#aiComposerHint').textContent='Dictando… revisa el texto y pulsa enviar.';
	};
	recognition.onresult=event=>{
		let transcript='';
		for(let index=0;index<event.results.length;index++){
			transcript+=event.results[index][0].transcript;
		}
		input.value=[baseText,transcript.trim()].filter(Boolean).join(' ');
		updateAiComposer();
		setAiSceneCaption(transcript.trim()||'Te escucho…');
	};
	recognition.onerror=event=>{
		const messages={
			'not-allowed':'Permite el acceso al micrófono en el navegador para usar el dictado.',
			'service-not-allowed':'El navegador no permitió iniciar el reconocimiento de voz.',
			'no-speech':'No se detectó voz. Inténtalo otra vez.',
			'network':'El servicio de reconocimiento de voz no está disponible en este momento.',
			'audio-capture':'No se encontró un micrófono disponible.',
			'aborted':'Se canceló el dictado.',
		};
		const message=messages[event.error]||`No se pudo reconocer la voz (${event.error}).`;
		recognitionError=event.error!=='aborted';
		setAiStatus(message,event.error!=='aborted');
		setAiSceneCaption(event.error==='no-speech'?'No alcancé a escucharte.':message);
		if(event.error!=='aborted')setAiFaceState('error','El dictado encontró un error');
	};
	recognition.onend=()=>{
		aiState.listening=false;
		aiState.recognition=null;
		updateAiVoiceControls();
		if(recognitionError){
			$('#aiComposerHint').textContent=input.value.trim()
				?'Dictado incompleto · revisa el texto antes de enviar'
				:'Enter envía · Shift+Enter añade una línea';
		}else if(input.value.trim()){
			setAiFaceState('idle','Asistente musical en espera');
			setAiSceneCaption('Te escuché. Revisa el texto y envíalo cuando quieras.');
			setAiStatus('Dictado listo. Revisa el texto antes de enviarlo.');
			$('#aiComposerHint').textContent='Dictado listo · Enter envía';
		}else{
			setAiFaceState('idle','Asistente musical en espera');
			setAiStatus('Dictado finalizado.');
			$('#aiComposerHint').textContent='Enter envía · Shift+Enter añade una línea';
		}
	};
	try{
		recognition.start();
	}catch(error){
		console.error('No se pudo iniciar el reconocimiento de voz:',error);
		setAiStatus('No se pudo iniciar el dictado. Revisa los permisos del micrófono e inténtalo de nuevo.',true);
		aiState.listening=false;
		aiState.recognition=null;
		updateAiVoiceControls();
	}
}
function appendInlineFormatting(container,text){
	const tokenPattern=/(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\*[^*]+\*|_[^_]+_)/g;
	let position=0,match;
	while((match=tokenPattern.exec(text))){
		container.append(document.createTextNode(text.slice(position,match.index)));
		const token=match[0],element=document.createElement(
			token.startsWith('**')||token.startsWith('__')?'strong':
			token.startsWith('`')?'code':'em'
		);
		element.textContent=token.startsWith('**')||token.startsWith('__')?token.slice(2,-2):token.slice(1,-1);
		container.append(element);
		position=tokenPattern.lastIndex;
	}
	container.append(document.createTextNode(text.slice(position)));
}
function renderAiFormattedContent(container,content){
	let paragraph=[];
	let list=null,listType='';
	const flushParagraph=()=>{
		if(!paragraph.length)return;
		const block=document.createElement('p');
		block.className='ai-content-paragraph';
		paragraph.forEach((line,index)=>{
			if(index)block.append(document.createElement('br'));
			appendInlineFormatting(block,line);
		});
		container.append(block);
		paragraph=[];
	};
	const flushList=()=>{
		if(list)container.append(list);
		list=null;
		listType='';
	};
	for(const line of content.replace(/\r/g,'').split('\n')){
		const heading=line.match(/^#{1,3}\s+(.+)$/);
		const ordered=line.match(/^\s*\d+[.)]\s+(.+)$/);
		const unordered=line.match(/^\s*[-*]\s+(.+)$/);
		if(!line.trim()){
			flushParagraph();
			flushList();
			continue;
		}
		if(heading){
			flushParagraph();
			flushList();
			const block=document.createElement('h3');
			appendInlineFormatting(block,heading[1]);
			container.append(block);
			continue;
		}
		if(ordered||unordered){
			flushParagraph();
			const nextType=ordered?'ol':'ul';
			if(nextType!==listType)flushList();
			if(!list){
				list=document.createElement(nextType);
				list.className='ai-content-list';
				listType=nextType;
			}
			const item=document.createElement('li');
			appendInlineFormatting(item,(ordered||unordered)[1]);
			list.append(item);
			continue;
		}
		flushList();
		paragraph.push(line);
	}
	flushParagraph();
	flushList();
}
function appendAiMessage(role,content,options={}){
	const article=document.createElement('article');
	article.className=`ai-message ai-message--${role}${options.pending?' ai-message--pending':''}`;
	const header=document.createElement('header');
	header.className='ai-message-header';
	const label=document.createElement('span');
	label.className='ai-message-label';
	label.textContent=role==='user'?'Tú':$('#aiAssistantName').textContent;
	header.append(label);
	if(role==='assistant'&&!options.pending){
		const listen=document.createElement('button');
		listen.type='button';
		listen.className='ai-message-speak';
		listen.textContent='◖ Leer';
		listen.setAttribute('aria-label','Leer respuesta en voz alta');
		listen.disabled=!supportsSpeechOutput;
		listen.title=supportsSpeechOutput?'Leer respuesta en voz alta':'La lectura en voz alta no está disponible en este navegador';
		listen.onclick=()=>speakAiText(content,listen);
		const copy=document.createElement('button');
		copy.type='button';
		copy.className='ai-message-copy';
		copy.textContent='Copiar';
		copy.setAttribute('aria-label','Copiar respuesta');
		copy.onclick=async()=>{
			try{
				await navigator.clipboard.writeText(content);
				toast('Respuesta copiada.');
			}catch(error){
				console.error('No se pudo copiar la respuesta:',error);
				toast('No se pudo copiar. Selecciona el texto y cópialo manualmente.');
			}
		};
		header.append(listen,copy);
	}
	const body=document.createElement('div');
	body.className='ai-message-content';
	if(options.pending)body.textContent=content;
	else renderAiFormattedContent(body,content);
	article.append(header,body);
	aiMessages.append(article);
	aiMessages.scrollTop=aiMessages.scrollHeight;
	return article;
}
function showAiWelcome(){
	aiMessages.replaceChildren();
	appendAiMessage('assistant','Hola. Puedo ayudarte a explorar teoría musical y crear borradores de ejercicios, actividades e ideas de composición para que los revises. Por ahora trabajo solo con texto: todavía no puedo analizar partituras o archivos ni generar notación reproducible.');
	$('#aiSuggestions').hidden=false;
}
function renderAiConversationList(){
	const list=$('#aiConversationList');
	list.replaceChildren();
	const query=$('#aiConversationSearch').value.trim().toLocaleLowerCase();
	const filtered=aiState.conversations.filter(conversation=>conversation.titulo.toLocaleLowerCase().includes(query));
	if(!filtered.length){
		const empty=document.createElement('p');
		empty.className='ai-history-empty';
		empty.textContent=query?'No hay conversaciones con ese nombre.':'Tus conversaciones aparecerán aquí.';
		list.append(empty);
		return;
	}
	filtered.forEach(conversation=>{
		const row=document.createElement('div');
		row.className='ai-conversation-row';
		const button=document.createElement('button');
		button.type='button';
		button.className='ai-conversation-item';
		button.classList.toggle('active',Number(conversation.id_conversacion)===aiState.conversationId);
		button.disabled=aiState.busy;
		button.textContent=conversation.titulo;
		button.title=conversation.titulo;
		button.onclick=()=>loadAiConversation(Number(conversation.id_conversacion));
		const remove=document.createElement('button');
		remove.type='button';
		remove.className='ai-conversation-delete';
		remove.disabled=aiState.busy;
		remove.textContent='×';
		remove.setAttribute('aria-label',`Eliminar conversación: ${conversation.titulo}`);
		remove.onclick=()=>deleteAiConversation(Number(conversation.id_conversacion));
		row.append(button,remove);
		list.append(row);
	});
}
async function refreshAiConversations(){
	const data=await api('/api/ai/conversations');
	aiState.conversations=data.conversations||[];
	renderAiConversationList();
}
async function loadAiConversation(id){
	if(aiState.busy)return;
	try{
		const data=await api(`/api/ai/conversations/${id}`);
		aiState.conversationId=Number(data.conversation.id_conversacion);
		aiMessages.replaceChildren();
		if(data.messages.length){
			data.messages.forEach(message=>appendAiMessage(message.rol,message.contenido));
			$('#aiSuggestions').hidden=true;
		}else showAiWelcome();
		renderAiConversationList();
		setAiFaceState('idle','Asistente musical en espera');
	}catch(error){
		setAiStatus(error.message,true);
	}
}
async function deleteAiConversation(id){
	if(aiState.busy)return;
	if(!confirm('¿Eliminar esta conversación y sus mensajes? Esta acción no se puede deshacer.'))return;
	try{
		await api(`/api/ai/conversations/${id}`,{method:'DELETE'});
		if(aiState.conversationId===id)aiState.conversationId=null;
		await refreshAiConversations();
		if(aiState.conversations.length)await loadAiConversation(Number(aiState.conversations[0].id_conversacion));
		else showAiWelcome();
	}catch(error){
		setAiStatus(error.message,true);
	}
}
async function loadAiWorkspace(){
	if(!state.user){
		setAiStatus('Inicia sesión para usar el asistente.',true);
		return;
	}
	showAiWelcomeOnce();
	try{
		const config=await api('/api/ai/config');
		$('#aiAssistantName').textContent=config.assistant_name;
		$('#aiPageTitle').textContent=config.assistant_name;
		aiState.configured=config.configured;
		configureAiProviders(config);
		configureAiLevel(config);
		renderAiSuggestions(config.role);
		updateAiVoiceControls();
		$('#aiMessageInput').disabled=!config.configured;
		$('#aiSendButton').disabled=!config.configured;
		$('#aiNewConversation').disabled=!config.configured;
		$$('[data-ai-prompt]').forEach(button=>button.disabled=!config.configured);
		if(config.configured)updateAiProviderStatus();
		else setAiStatus('No hay proveedores configurados. Añade OPENAI_API_KEY o GEMINI_API_KEY al .env del servidor.',true);
		await refreshAiConversations();
		if(aiState.conversationId&&aiState.conversations.some(item=>Number(item.id_conversacion)===aiState.conversationId)){
			await loadAiConversation(aiState.conversationId);
		}else if(aiState.conversations.length){
			await loadAiConversation(Number(aiState.conversations[0].id_conversacion));
		}else{
			aiState.conversationId=null;
			showAiWelcome();
		}
	}catch(error){
		setAiStatus(error.message,true);
	}
}
async function createAiConversation(){
	if(aiState.busy||!aiState.configured)return;
	try{
		const data=await api('/api/ai/conversations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
		aiState.conversationId=Number(data.id_conversacion);
		$('#aiConversationSearch').value='';
		await refreshAiConversations();
		showAiWelcome();
		$('#aiMessageInput').focus();
	}catch(error){
		setAiStatus(error.message,true);
	}
}
$('#aiNewConversation').onclick=createAiConversation;
$('#aiProviderSelect').onchange=()=>{
	aiState.provider=$('#aiProviderSelect').value;
	try{
		localStorage.setItem('lyrics.ai.provider.v1',aiState.provider);
	}catch(error){
		console.error('No se pudo guardar el proveedor de IA seleccionado:',error);
		toast('No se pudo guardar la preferencia del proveedor.');
	}
	updateAiProviderStatus();
};
$('#aiVoiceOutput').onclick=()=>setVoiceOutput(!aiState.voiceOutput);
$('#aiMicButton').onclick=startAiListening;
$('#aiMinimizeButton').onclick=()=>{
	const minimized=$('.ai-chat').classList.toggle('is-minimized');
	const button=$('#aiMinimizeButton');
	button.setAttribute('aria-expanded',String(!minimized));
	button.setAttribute('aria-label',minimized?'Restaurar asistente':'Minimizar asistente');
	button.title=minimized?'Restaurar':'Minimizar';
	button.textContent=minimized?'□':'−';
	if(minimized)stopAiListening();
};
$('#aiCloseButton').onclick=()=>{
	stopAiListening();
	stopAiSpeech();
	setView('dashboard');
};
$('#aiConversationSearch').oninput=renderAiConversationList;
// Delegación de eventos: las sugerencias se vuelven a crear según el rol de la persona.
$('#aiSuggestions').onclick=event=>{
	const button=event.target.closest('[data-ai-prompt]');
	if(!button||!aiState.configured)return;
	$('#aiMessageInput').value=button.dataset.aiPrompt;
	updateAiComposer();
	$('#aiMessageInput').focus();
};
$('#aiLevelSelect').onchange=async()=>{
	const select=$('#aiLevelSelect'),previous=select.dataset.saved;
	select.disabled=true;
	setAiStatus('Guardando tu nivel…');
	try{
		await api('/api/ai/preferences',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({nivel:select.value})});
		select.dataset.saved=select.value;
		setAiStatus(`Nivel guardado: ${AI_LEVEL_LABELS[select.value]||select.value}. Las próximas respuestas se adaptarán.`);
	}catch(error){
		select.value=previous; // se revierte para que la pantalla refleje lo que sí quedó guardado
		setAiStatus(`No se pudo guardar el nivel: ${error.message}`,true);
	}finally{
		select.disabled=aiState.busy;
	}
};
$('#aiMessageInput').onkeydown=event=>{
	if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){
		event.preventDefault();
		$('#aiMessageForm').requestSubmit();
	}
};
function updateAiComposer(){
	const input=$('#aiMessageInput');
	input.style.height='auto';
	input.style.height=`${Math.min(input.scrollHeight,160)}px`;
	$('#aiCharacterCount').textContent=`${input.value.length} / 4.000`;
}
$('#aiMessageInput').oninput=updateAiComposer;
$('#aiMessageInput').onpaste=()=>window.setTimeout(updateAiComposer,0);
$('#aiMessageForm').onsubmit=async event=>{
	event.preventDefault();
	if(aiState.listening){
		stopAiListening();
		setAiStatus('Finaliza el dictado y revisa el texto antes de enviarlo.');
		return;
	}
	const input=$('#aiMessageInput'),content=input.value.trim();
	if(!content||aiState.busy)return;
	if(!aiState.configured){
		setAiStatus('No hay proveedores configurados. Añade OPENAI_API_KEY o GEMINI_API_KEY al .env del servidor.',true);
		return;
	}
	const provider=selectedAiProvider();
	if(!provider){
		setAiStatus('El proveedor seleccionado no está configurado. Elige otro proveedor.',true);
		return;
	}
	aiState.busy=true;
	$('#aiProviderSelect').disabled=true;
	updateAiVoiceControls();
	$('#aiSendButton').disabled=true;
	$('#aiMessageInput').disabled=true;
	$('#aiNewConversation').disabled=true;
	$$('.ai-conversation-item,.ai-conversation-delete').forEach(button=>button.disabled=true);
	$('#aiSuggestions').hidden=true;
	if(!aiState.conversationId){
		try{
			const conversation=await api('/api/ai/conversations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
			aiState.conversationId=Number(conversation.id_conversacion);
		}catch(error){
			setAiStatus(error.message,true);
			aiState.busy=false;
			$('#aiSendButton').disabled=false;
			$('#aiMessageInput').disabled=false;
			$('#aiNewConversation').disabled=false;
			$$('.ai-conversation-item,.ai-conversation-delete').forEach(button=>button.disabled=false);
			$('#aiProviderSelect').disabled=!aiState.configured||aiState.providers.length<2;
			updateAiVoiceControls();
			return;
		}
	}
	appendAiMessage('user',content);
	const pending=appendAiMessage('assistant','Preparando una respuesta…',{pending:true});
	input.value='';
	updateAiComposer();
	setAiFaceState('thinking','Asistente musical procesando el mensaje');
	setAiStatus('Preparando una respuesta…');
	try{
		const data=await api(`/api/ai/conversations/${aiState.conversationId}/messages`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({contenido:content,provider:provider.id})});
		pending.remove();
		appendAiMessage('assistant',data.reply);
		setAiFaceState('success','Asistente musical terminó de responder');
		setAiSceneCaption(data.provider_used==='local'
			?'Respuesta musical local de respaldo.'
			:'Aquí tienes una idea para explorar.');
		if(data.fallback_notice){
			setAiStatus(data.fallback_notice,data.provider_used==='local'&&provider.id!=='local');
		}else if(data.provider_used!==provider.id){
			setAiStatus(`Respuesta recibida de ${data.provider_used}.`);
		}else{
			setAiStatus('Respuesta lista · revisa los borradores antes de usarlos.');
		}
		if(aiState.voiceOutput)speakAiText(data.reply);
		try{
			await refreshAiConversations();
		}catch(error){
			console.error('No se pudo actualizar el historial de conversaciones:',error);
			setAiStatus('La respuesta se guardó, pero no se pudo actualizar el historial.',true);
		}
	}catch(error){
		pending.remove();
		appendAiMessage('assistant',`No se pudo completar la solicitud: ${error.message}`);
		input.value=content;
		setAiFaceState('error','El asistente encontró un error');
		setAiStatus(error.message,true);
		$('#aiSuggestions').hidden=false;
	}finally{
		aiState.busy=false;
		$('#aiSendButton').disabled=!aiState.configured;
		$('#aiMessageInput').disabled=!aiState.configured;
		$('#aiNewConversation').disabled=!aiState.configured;
		$('#aiProviderSelect').disabled=!aiState.configured||aiState.providers.length<2;
		$$('.ai-conversation-item,.ai-conversation-delete').forEach(button=>button.disabled=false);
		updateAiVoiceControls();
		updateAiComposer();
		if(aiState.configured)input.focus();
	}
};

updateAiVoiceControls();
if(window.matchMedia('(prefers-reduced-motion: reduce)').matches)setAiFaceState('rest','Asistente musical en reposo');
