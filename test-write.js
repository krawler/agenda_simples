import { collection, addDoc, serverTimestamp } from "firebase/firestore";
import { db } from "./firebase/config.js";

async function testarFirestore() {
  try {
    const docRef = await addDoc(collection(db, "eventos"), {
      titulo: "Teste Firebase",
      inicio: "2026-08-20T10:00:00",
      duracaoMinutos: 60,
      descricao: "Teste de sincronização",
      createdAt: serverTimestamp()
    });

    console.log("Documento criado com id:", docRef.id);
  } catch (error) {
    console.error("Erro ao gravar:", error);
  }
}

testarFirestore();